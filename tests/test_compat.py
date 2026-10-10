"""Differential tests: every public function must agree with phonenumbers."""

import pickle
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("phonenumbers")

import phonenumbers  # noqa: E402
import rphonenumbers  # noqa: E402
from differential import run_all  # noqa: E402

CHECKED = (
    "COUNTRY_CODES_FOR_NON_GEO_REGIONS",
    "COUNTRY_CODE_TO_REGION_CODE",
    "NON_DIGITS_PATTERN",
    "PhoneNumberMatcher",
    "REGION_CODE_FOR_NON_GEO_ENTITY",
    "SUPPORTED_REGIONS",
    "UNKNOWN_REGION",
    "can_be_internationally_dialled",
    "carrier.name_for_number",
    "carrier.safe_display_name",
    "convert_alpha_characters_in_number",
    "country_code_for_region",
    "country_code_for_valid_region",
    "country_mobile_token",
    "example_number",
    "example_number_for_non_geo_entity",
    "example_number_for_type",
    "expected_cost",
    "expected_cost_for_region",
    "format_by_pattern",
    "format_in_original_format",
    "format_national_number_with_carrier_code",
    "format_national_number_with_preferred_carrier_code",
    "format_number",
    "format_number_for_mobile_dialing",
    "format_out_of_country_calling_number",
    "format_out_of_country_keeping_alpha_chars",
    "geocoder.country_name_for_number",
    "geocoder.description_for_number",
    "invalid_example_number",
    "is_alpha_number",
    "is_carrier_specific",
    "is_carrier_specific_for_region",
    "is_mobile_number_portable_region",
    "is_nanpa_country",
    "is_number_geographical",
    "is_number_match",
    "is_number_type_geographical",
    "is_possible_number",
    "is_possible_number_for_type",
    "is_possible_number_for_type_with_reason",
    "is_possible_number_string",
    "is_possible_number_with_reason",
    "is_possible_short_number",
    "is_possible_short_number_for_region",
    "is_sms_service_for_region",
    "is_valid_number",
    "is_valid_number_for_region",
    "is_valid_short_number",
    "is_valid_short_number_for_region",
    "length_of_geographical_area_code",
    "length_of_national_destination_code",
    "national_significant_number",
    "ndd_prefix_for_region",
    "normalize_diallable_chars_only",
    "normalize_digits_only",
    "number_type",
    "parse",
    "region_code_for_country_code",
    "region_code_for_number",
    "region_codes_for_country_code",
    "supported_calling_codes",
    "supported_types_for_non_geo_entity",
    "supported_types_for_region",
    "timezone.time_zones_for_geographical_number",
    "timezone.time_zones_for_number",
    "truncate_too_long_number",
)

# Intentional, documented differences from phonenumbers.
KNOWN_DIVERGENCES = {
    # phonenumbers returns the first match while iterating SUPPORTED_REGIONS,
    # a set, so its answer depends on PYTHONHASHSEED. Checked separately below.
    "example_number": lambda args, expected, actual: args == (None,),
    # phonenumbers crashes on region_calling_from=None (None.upper()) when the
    # number has raw input; we return the international format instead.
    "format_out_of_country_keeping_alpha_chars": lambda args, expected, actual: (
        args[1] is None and expected == ("raised", "AttributeError")
    ),
}


@pytest.fixture(scope="module")
def recorder():
    return run_all()


def test_metadata_versions_match():
    assert phonenumbers.__version__ == rphonenumbers.__phonenumbers_version__


def test_every_comparison_is_listed(recorder):
    assert set(recorder.counts) == set(CHECKED)


@pytest.mark.parametrize("name", CHECKED)
def test_matches_phonenumbers(recorder, name):
    assert recorder.counts[name] > 0
    allowed = KNOWN_DIVERGENCES.get(name, lambda *_: False)
    unexplained = [m for m in recorder.mismatches.get(name, []) if not allowed(*m)]
    assert not unexplained, "%d of %d differ, first: %r" % (
        len(unexplained),
        recorder.counts[name],
        unexplained[:3],
    )


def test_example_number_anywhere_is_a_valid_fixed_line_number():
    numobj = rphonenumbers.example_number(None)
    assert rphonenumbers.is_valid_number(numobj)
    assert rphonenumbers.number_type(numobj) in (
        rphonenumbers.PhoneNumberType.FIXED_LINE,
        rphonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    )


def test_upstream_phone_number_objects_are_accepted():
    upstream = phonenumbers.parse("+41 44 668 1800")
    national = rphonenumbers.PhoneNumberFormat.NATIONAL
    assert rphonenumbers.format_number(upstream, national) == "044 668 18 00"
    assert rphonenumbers.is_valid_number(upstream)


def test_delegated_string_apis_match_phonenumbers():
    for number, region in (("112", "FI"), ("911", "US"), ("999", "GB"), ("9116", "US"), ("1234", "ZZ")):
        for name in ("is_emergency_number", "connects_to_emergency_number"):
            ours = getattr(rphonenumbers, name)(number, region)
            assert ours == getattr(phonenumbers, name)(number, region), (name, number, region)
    assert rphonenumbers.SUPPORTED_SHORT_REGIONS == phonenumbers.SUPPORTED_SHORT_REGIONS
    assert rphonenumbers.ShortNumberCost.PREMIUM_RATE == phonenumbers.ShortNumberCost.PREMIUM_RATE


def test_delegated_as_you_type_formatter():
    for region, digits in (("US", "16502530000"), ("GB", "02083661177"), ("DE", "+493012345678")):
        ours, theirs = rphonenumbers.AsYouTypeFormatter(region), phonenumbers.AsYouTypeFormatter(region)
        assert [ours.input_digit(d) for d in digits] == [theirs.input_digit(d) for d in digits]


def test_delegated_phone_metadata():
    from rphonenumbers.phonemetadata import PhoneMetadata
    from rphonenumbers.phonenumberutil import PhoneMetadata as from_util

    assert PhoneMetadata is from_util is rphonenumbers.PhoneMetadata
    assert PhoneMetadata.metadata_for_region("GB").country_code == 44


def test_install_aliases_delegated_modules():
    # NZ metadata is first loaded after install(), so this also checks that
    # phonenumbers' lazy loading keeps resolving inside its private copy.
    script = textwrap.dedent(
        """
        import rphonenumbers
        rphonenumbers.install()
        import phonenumbers
        import phonenumbers.geocoder
        from phonenumbers import carrier, timezone
        from phonenumbers.asyoutypeformatter import AsYouTypeFormatter
        from phonenumbers.phonemetadata import PhoneMetadata
        from phonenumbers.shortnumberinfo import is_valid_short_number
        assert phonenumbers is rphonenumbers
        numobj = phonenumbers.parse("+64 21 123 4567")
        assert type(numobj) is rphonenumbers.PhoneNumber
        print(phonenumbers.geocoder.description_for_number(numobj, "en"))
        print(carrier.name_for_number(numobj, "en"))
        print(timezone.time_zones_for_number(numobj))
        print(is_valid_short_number(phonenumbers.parse("111", "NZ")))
        print(PhoneMetadata.metadata_for_region("NZ").country_code)
        print(AsYouTypeFormatter("NZ").input_digit("0"))
        """
    )
    out = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
    from phonenumbers import carrier, geocoder, timezone

    numobj = phonenumbers.parse("+64 21 123 4567")
    expected = [
        geocoder.description_for_number(numobj, "en"),
        carrier.name_for_number(numobj, "en"),
        str(timezone.time_zones_for_number(numobj)),
        str(phonenumbers.is_valid_short_number(phonenumbers.parse("111", "NZ"))),
        "64",
        phonenumbers.AsYouTypeFormatter("NZ").input_digit("0"),
    ]
    assert out.stdout.splitlines() == expected


def test_delegated_objects_unpickle_in_a_fresh_process():
    formatter = rphonenumbers.AsYouTypeFormatter("US")
    formatter.input_digit("6")
    script = "import pickle, sys; print(pickle.loads(sys.stdin.buffer.read()).input_digit('5'))"
    out = subprocess.run(
        [sys.executable, "-c", script], input=pickle.dumps(formatter), check=True, capture_output=True
    )
    assert out.stdout.decode().strip() == "65"
