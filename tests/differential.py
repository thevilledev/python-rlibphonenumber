"""Differential comparison of rphonenumbers against upstream phonenumbers.

``run_all()`` feeds the shared corpus to both libraries and returns, per API
function, the list of inputs whose results differ. ``tests/test_compat.py``
asserts on it; running this module directly prints a summary.
"""

from collections import defaultdict

import phonenumbers as up
import rphonenumbers as rs
from corpus import ALL_TYPES, CALLING_FROM, EDGE_REGIONS, FORMATS, MATCHER_TEXTS, number_strings
from phonenumbers import carrier as up_carrier
from phonenumbers import geocoder as up_geocoder
from phonenumbers import timezone as up_timezone
from rphonenumbers import carrier as rs_carrier
from rphonenumbers import geocoder as rs_geocoder
from rphonenumbers import timezone as rs_timezone

FIELDS = (
    "country_code",
    "national_number",
    "extension",
    "italian_leading_zero",
    "number_of_leading_zeros",
    "raw_input",
    "country_code_source",
    "preferred_domestic_carrier_code",
)


def fields(numobj):
    return tuple(getattr(numobj, f) for f in FIELDS)


def normalize(value):
    """Turn a result (or raised exception) into a comparable value."""
    if isinstance(value, (up.PhoneNumber, rs.PhoneNumber)):
        return ("PhoneNumber", fields(value))
    if isinstance(value, (up.PhoneNumberMatch, rs.PhoneNumberMatch)):
        return ("Match", value.start, value.end, value.raw_string, fields(value.number))
    if isinstance(value, up.NumberParseException) or isinstance(value, rs.NumberParseException):
        return ("NumberParseException", value.error_type, value._msg)
    if isinstance(value, BaseException):
        return ("raised", type(value).__name__)
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted(value)))
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def call(fn, *args):
    try:
        return normalize(fn(*args))
    except Exception as exc:  # noqa: BLE001 - exceptions are part of the result
        return normalize(exc)


def to_rs(numobj):
    return rs.PhoneNumber(**dict(zip(FIELDS, fields(numobj), strict=True)))


class Recorder:
    def __init__(self):
        self.mismatches = defaultdict(list)
        self.counts = defaultdict(int)

    def check(self, name, args, expected, actual):
        self.counts[name] += 1
        if expected != actual:
            self.mismatches[name].append((args, expected, actual))

    def compare(self, name, args, rs_args=None):
        expected = call(getattr(up, name), *args)
        actual = call(getattr(rs, name), *(args if rs_args is None else rs_args))
        self.check(name, args, expected, actual)
        return expected


def compare_number_functions(rec, up_num):
    num = to_rs(up_num)
    one = (
        "can_be_internationally_dialled",
        "is_number_geographical",
        "is_possible_number",
        "is_possible_number_with_reason",
        "is_valid_number",
        "length_of_geographical_area_code",
        "length_of_national_destination_code",
        "national_significant_number",
        "number_type",
        "region_code_for_number",
    )
    for name in one:
        rec.compare(name, (up_num,), (num,))
    for fmt in FORMATS:
        rec.compare("format_number", (up_num, fmt), (num, fmt))
    for numtype in ALL_TYPES:
        rec.compare("is_possible_number_for_type", (up_num, numtype), (num, numtype))
        rec.compare("is_possible_number_for_type_with_reason", (up_num, numtype), (num, numtype))
    for region in CALLING_FROM:
        rec.compare("format_out_of_country_calling_number", (up_num, region), (num, region))
        rec.compare("format_out_of_country_keeping_alpha_chars", (up_num, region), (num, region))
        rec.compare("format_in_original_format", (up_num, region), (num, region))
        rec.compare("is_valid_number_for_region", (up_num, region), (num, region))
        for with_formatting in (True, False):
            rec.compare(
                "format_number_for_mobile_dialing",
                (up_num, region, with_formatting),
                (num, region, with_formatting),
            )
    for carrier in ("", "15", "41"):
        rec.compare("format_national_number_with_carrier_code", (up_num, carrier), (num, carrier))
        rec.compare("format_national_number_with_preferred_carrier_code", (up_num, carrier), (num, carrier))
    # truncate_too_long_number mutates its argument; compare result and state.
    up_copy, rs_copy = up.PhoneNumber(), to_rs(up_num)
    up_copy.merge_from(up_num)
    expected = (call(up.truncate_too_long_number, up_copy), fields(up_copy))
    actual = (call(rs.truncate_too_long_number, rs_copy), fields(rs_copy))
    rec.check("truncate_too_long_number", (up_num,), expected, actual)


# Submodules rphonenumbers takes from phonenumbers, as (phonenumbers, rphonenumbers).
DELEGATED_MODULES = {
    "carrier": (up_carrier, rs_carrier),
    "geocoder": (up_geocoder, rs_geocoder),
    "timezone": (up_timezone, rs_timezone),
}


def compare_delegated(rec, up_num):
    """The APIs taken from phonenumbers, called with rphonenumbers' own PhoneNumber objects."""
    num = to_rs(up_num)
    for name in ("is_valid_short_number", "is_possible_short_number", "expected_cost", "is_carrier_specific"):
        rec.compare(name, (up_num,), (num,))
    for region in CALLING_FROM:
        for name in (
            "is_valid_short_number_for_region",
            "is_possible_short_number_for_region",
            "expected_cost_for_region",
            "is_carrier_specific_for_region",
            "is_sms_service_for_region",
        ):
            rec.compare(name, (up_num, region), (num, region))
    for module, name, extra in (
        ("geocoder", "description_for_number", ("en",)),
        ("geocoder", "country_name_for_number", ("en",)),
        ("carrier", "name_for_number", ("en",)),
        ("carrier", "safe_display_name", ("en",)),
        ("timezone", "time_zones_for_number", ()),
        ("timezone", "time_zones_for_geographical_number", ()),
    ):
        up_module, rs_module = DELEGATED_MODULES[module]
        expected = call(getattr(up_module, name), up_num, *extra)
        actual = call(getattr(rs_module, name), num, *extra)
        rec.check("%s.%s" % (module, name), (up_num,) + extra, expected, actual)


def compare_parsing(rec, pairs):
    parsed = []
    for text, region in pairs:
        for keep in (False, True):
            expected = rec.compare("parse", (text, region, keep))
            if expected[0] == "PhoneNumber":
                parsed.append(up.parse(text, region, keep))
        rec.compare("is_possible_number_string", (text, region))
        rec.compare("normalize_digits_only", (text,))
        rec.compare("normalize_digits_only", (text, True))
        rec.compare("normalize_diallable_chars_only", (text,))
        rec.compare("convert_alpha_characters_in_number", (text,))
        rec.compare("is_alpha_number", (text,))
    return parsed


USER_FORMATS = [
    dict(pattern="(\\d{3})(\\d{3})(\\d{4})", format="(\\1) \\2-\\3"),
    dict(pattern="(\\d{2})(\\d{2,})", format="\\1-\\2", national_prefix_formatting_rule="$NP$FG"),
    dict(
        pattern="(\\d)(\\d+)",
        format="\\g<1> \\2 $",
        leading_digits_pattern=["[1-9]"],
        national_prefix_formatting_rule="($NP$FG)",
    ),
    dict(
        pattern="(\\d{2})(\\d{4})(\\d+)",
        format="\\1 \\2 \\3",
        domestic_carrier_code_formatting_rule="$NP $CC $FG",
        national_prefix_optional_when_formatting=True,
    ),
    dict(pattern="(\\d{4})(\\d+)", format="\\1/\\2", leading_digits_pattern=["9", "[2-8]"]),
]


def compare_format_by_pattern(rec, parsed):
    for up_num in parsed[::25]:
        num = to_rs(up_num)
        for i in range(len(USER_FORMATS)):
            subset = USER_FORMATS[i:] + USER_FORMATS[:i]
            up_fmts = [up.NumberFormat(**kw) for kw in subset]
            rs_fmts = [rs.NumberFormat(**kw) for kw in subset]
            for fmt in FORMATS:
                rec.compare("format_by_pattern", (up_num, fmt, up_fmts), (num, fmt, rs_fmts))


def compare_matching(rec, pairs, parsed):
    strings = [text for text, _ in pairs[::7]]
    for i, s1 in enumerate(strings):
        s2 = strings[(i * 31 + 7) % len(strings)]
        rec.compare("is_number_match", (s1, s2))
        rec.compare("is_number_match", (s1, s1))
    for i, n1 in enumerate(parsed[::5]):
        n2 = parsed[(i * 17 + 3) % len(parsed)]
        rec.compare("is_number_match", (n1, n2), (to_rs(n1), to_rs(n2)))
        rec.compare(
            "is_number_match", (n1, strings[i % len(strings)]), (to_rs(n1), strings[i % len(strings)])
        )


def compare_regions(rec):
    regions = sorted(up.SUPPORTED_REGIONS) + list(EDGE_REGIONS)
    for region in regions:
        for name in (
            "country_code_for_region",
            "country_code_for_valid_region",
            "is_nanpa_country",
            "example_number",
            "invalid_example_number",
            "supported_types_for_region",
            "is_mobile_number_portable_region",
        ):
            rec.compare(name, (region,))
        for strip in (True, False):
            rec.compare("ndd_prefix_for_region", (region, strip))
        for numtype in ALL_TYPES:
            if region is not None:
                rec.compare("example_number_for_type", (region, numtype))


def compare_calling_codes(rec):
    codes = sorted(up.COUNTRY_CODE_TO_REGION_CODE) + [0, 2, 999, 1000, -1]
    for code in codes:
        for name in (
            "region_code_for_country_code",
            "region_codes_for_country_code",
            "supported_types_for_non_geo_entity",
            "example_number_for_non_geo_entity",
            "country_mobile_token",
        ):
            rec.compare(name, (code,))
        for numtype in ALL_TYPES:
            rec.compare("is_number_type_geographical", (numtype, code))


def compare_constants(rec):
    for name in (
        "COUNTRY_CODE_TO_REGION_CODE",
        "SUPPORTED_REGIONS",
        "COUNTRY_CODES_FOR_NON_GEO_REGIONS",
        "UNKNOWN_REGION",
        "REGION_CODE_FOR_NON_GEO_ENTITY",
    ):
        rec.check(name, (), normalize(getattr(up, name)), normalize(getattr(rs, name)))
    rec.check("NON_DIGITS_PATTERN", (), up.NON_DIGITS_PATTERN.pattern, rs.NON_DIGITS_PATTERN.pattern)
    rec.check(
        "supported_calling_codes",
        (),
        normalize(up.supported_calling_codes()),
        normalize(rs.supported_calling_codes()),
    )


def find_all(lib, text, region, leniency):
    return list(lib.PhoneNumberMatcher(text, region, leniency))


def compare_matcher(rec):
    for text in MATCHER_TEXTS:
        for region in ("US", "GB", "DE", "CH", "FR", None, "ZZ"):
            for leniency in (0, 1, 2, 3):
                args = (text, region, leniency)
                rec.check("PhoneNumberMatcher", args, call(find_all, up, *args), call(find_all, rs, *args))


def run_all():
    rec = Recorder()
    pairs = number_strings()
    parsed = compare_parsing(rec, pairs)
    seen = set()
    for numobj in parsed:
        key = fields(numobj)
        if key not in seen:
            seen.add(key)
            compare_number_functions(rec, numobj)
            compare_delegated(rec, numobj)
    compare_format_by_pattern(rec, parsed)
    compare_matching(rec, pairs, parsed)
    compare_regions(rec)
    compare_calling_codes(rec)
    compare_constants(rec)
    compare_matcher(rec)
    return rec


if __name__ == "__main__":
    import sys

    result = run_all()
    total = sum(result.counts.values())
    bad = sum(len(v) for v in result.mismatches.values())
    print("%d comparisons, %d mismatches" % (total, bad))
    for name in sorted(result.counts):
        miss = result.mismatches.get(name, [])
        flag = "  " if not miss else "!!"
        print("%s %-55s %7d checked %6d differ" % (flag, name, result.counts[name], len(miss)))
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for name, miss in sorted(result.mismatches.items()):
        print("\n==", name)
        for args, expected, actual in miss[:limit]:
            print("  args    :", args)
            print("  expected:", expected)
            print("  actual  :", actual)
