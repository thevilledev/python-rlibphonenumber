"""Behavioural tests that do not need the upstream phonenumbers package."""

import doctest
import importlib.metadata
import pickle
import re
import subprocess
import sys
import textwrap

import pytest
import rphonenumbers as pn
from packaging.version import Version
from rphonenumbers import (
    FrozenPhoneNumber,
    NumberFormat,
    NumberParseException,
    PhoneNumber,
    PhoneNumberFormat,
    PhoneNumberType,
)


def test_package_doctests():
    failures, tests = doctest.testmod(pn)
    assert tests > 0
    assert failures == 0


def test_version_matches_distribution_metadata():
    assert Version(pn.__version__) == Version(importlib.metadata.version("rphonenumbers"))


def test_parse_and_format():
    numobj = pn.parse("020 8366 1177", "GB")
    assert numobj == PhoneNumber(country_code=44, national_number=2083661177)
    assert pn.format_number(numobj, PhoneNumberFormat.E164) == "+442083661177"
    assert pn.format_number(numobj, PhoneNumberFormat.INTERNATIONAL) == "+44 20 8366 1177"
    assert pn.format_number(numobj, PhoneNumberFormat.NATIONAL) == "020 8366 1177"
    assert pn.format_number(numobj, PhoneNumberFormat.RFC3966) == "tel:+44-20-8366-1177"
    assert pn.is_valid_number(numobj)
    assert pn.number_type(numobj) == PhoneNumberType.FIXED_LINE
    assert pn.region_code_for_number(numobj) == "GB"


def test_parsed_objects_are_plain_phone_numbers():
    numobj = pn.parse("+1 650 253 0000 ext. 12", keep_raw_input=True)
    assert type(numobj) is PhoneNumber
    assert numobj.__dict__ == {
        "country_code": 1,
        "national_number": 6502530000,
        "extension": "12",
        "italian_leading_zero": None,
        "number_of_leading_zeros": None,
        "raw_input": "+1 650 253 0000 ext. 12",
        "country_code_source": pn.CountryCodeSource.FROM_NUMBER_WITH_PLUS_SIGN,
        "preferred_domestic_carrier_code": None,
    }
    assert str(numobj) == ("Country Code: 1 National Number: 6502530000 Extension: 12 Country Code Source: 1")


def test_italian_leading_zeros():
    numobj = pn.parse("+39 0236618300")
    assert numobj.italian_leading_zero is True
    assert pn.national_significant_number(numobj) == "0236618300"


NOT_A_NUMBER = "The string supplied did not seem to be a phone number."
MISSING_REGION = "Missing or invalid default region."
AFTER_PLUS = "Could not interpret numbers after plus-sign."
TOO_SHORT_NSN = "The string supplied is too short to be a phone number."
TOO_SHORT_IDD = "Phone number had an IDD, but after this was not long enough to be a viable phone number."


@pytest.mark.parametrize(
    "number, region, error_type, message",
    [
        (None, "US", NumberParseException.NOT_A_NUMBER, "The phone number supplied was None."),
        ("abc", "US", NumberParseException.NOT_A_NUMBER, NOT_A_NUMBER),
        ("650 253 0000", None, NumberParseException.INVALID_COUNTRY_CODE, MISSING_REGION),
        ("650 253 0000", "us", NumberParseException.INVALID_COUNTRY_CODE, MISSING_REGION),
        ("+999 1234567", None, NumberParseException.INVALID_COUNTRY_CODE, AFTER_PLUS),
        ("1", "US", NumberParseException.NOT_A_NUMBER, NOT_A_NUMBER),
        ("+44 1", None, NumberParseException.TOO_SHORT_NSN, TOO_SHORT_NSN),
        ("9" * 251, "US", NumberParseException.TOO_LONG, "The string supplied was too long to parse."),
        ("011 44", "US", NumberParseException.TOO_SHORT_AFTER_IDD, TOO_SHORT_IDD),
    ],
)
def test_parse_errors(number, region, error_type, message):
    with pytest.raises(NumberParseException) as info:
        pn.parse(number, region)
    assert info.value.error_type == error_type
    assert info.value._msg == message
    assert str(info.value) == "(%d) %s" % (error_type, message)


def test_parse_exception_pickles():
    exc = NumberParseException(NumberParseException.TOO_LONG, "msg")
    clone = pickle.loads(pickle.dumps(exc))
    assert (clone.error_type, clone._msg, str(clone)) == (exc.error_type, exc._msg, str(exc))


def test_parse_into_existing_numobj():
    target = PhoneNumber(extension="5")
    result = pn.parse("+44 20 8366 1177", numobj=target)
    assert result is target
    # Like phonenumbers, fields the parse does not set are left untouched.
    assert (target.country_code, target.national_number, target.extension) == (44, 2083661177, "5")


def test_user_built_numbers_are_accepted():
    numobj = PhoneNumber(country_code=41, national_number=446681800)
    assert pn.format_number(numobj, PhoneNumberFormat.NATIONAL) == "044 668 18 00"
    assert pn.is_valid_number_for_region(numobj, "CH")
    assert not pn.is_valid_number_for_region(numobj, "DE")


def test_frozen_phone_number():
    frozen = FrozenPhoneNumber(pn.parse("+1 650 253 0000"))
    assert frozen == pn.parse("+1 650 253 0000")
    assert hash(frozen) == hash(FrozenPhoneNumber(country_code=1, national_number=6502530000))
    assert {frozen: 1}[FrozenPhoneNumber(pn.parse("+1 650 253 0000"))] == 1
    with pytest.raises(TypeError):
        frozen.extension = "1"
    with pytest.raises(TypeError):
        hash(PhoneNumber())


def test_truncate_too_long_number_mutates():
    numobj = PhoneNumber(country_code=1, national_number=65025300001)
    assert pn.truncate_too_long_number(numobj)
    assert numobj.national_number == 6502530000


def test_format_by_pattern_uses_python_templates():
    numobj = pn.parse("+1 650 253 0000")
    fmt = NumberFormat(pattern="(\\d{3})(\\d{3})(\\d{4})", format="(\\1) \\2-\\3")
    assert pn.format_by_pattern(numobj, PhoneNumberFormat.NATIONAL, [fmt]) == "(650) 253-0000"
    numobj.extension = "7"
    assert pn.format_by_pattern(numobj, PhoneNumberFormat.RFC3966, [fmt]) == "tel:+1-650-253-0000;ext=7"


def test_format_by_pattern_rejects_invalid_regex():
    numobj = pn.parse("+1 650 253 0000")
    with pytest.raises(re.error):
        pn.format_by_pattern(numobj, PhoneNumberFormat.NATIONAL, [NumberFormat(pattern="(\\d", format="\\1")])


def test_matcher_reports_character_offsets():
    text = "Zürich → +41 44 668 18 00, then 044 668 18 00."
    matches = list(pn.PhoneNumberMatcher(text, "CH"))
    assert [(m.start, m.end, m.raw_string) for m in matches] == [
        (9, 25, "+41 44 668 18 00"),
        (32, 45, "044 668 18 00"),
    ]
    for m in matches:
        assert text[m.start : m.end] == m.raw_string
        assert m.number == PhoneNumber(country_code=41, national_number=446681800)
    assert str(matches[0]) == "PhoneNumberMatch [9,25) +41 44 668 18 00"


def test_matcher_iteration_protocol():
    matcher = pn.PhoneNumberMatcher("Call 650-253-0000 or 650-253-0001", "US", pn.Leniency.POSSIBLE)
    assert matcher.has_next()
    assert matcher.next().raw_string == "650-253-0000"
    assert matcher.next().raw_string == "650-253-0001"
    assert not matcher.has_next()
    with pytest.raises(StopIteration):
        matcher.next()
    with pytest.raises(ValueError):
        pn.PhoneNumberMatcher("", "US", max_tries=-1)


def test_is_number_match_mixed_arguments():
    numobj = pn.parse("+1 650 253 0000")
    assert pn.is_number_match(numobj, "+1 650 253 0000") == pn.MatchType.EXACT_MATCH
    assert pn.is_number_match("650 253 0000", numobj) == pn.MatchType.NSN_MATCH
    assert pn.is_number_match("abc", "def") == pn.MatchType.NOT_A_NUMBER


def test_enum_helpers():
    assert PhoneNumberType.to_string(PhoneNumberType.VOIP) == "VOIP"
    assert PhoneNumberType.to_string(42) == "INVALID (42)"
    assert PhoneNumberType.values()[-1] == PhoneNumberType.UNKNOWN
    assert pn.ValidationResult.to_string(pn.ValidationResult.TOO_LONG) == "TOO_LONG"


def test_unknown_names_raise_attribute_error():
    with pytest.raises(AttributeError, match="has no attribute"):
        _ = pn.definitely_not_there


def test_delegated_apis_explain_missing_phonenumbers():
    script = textwrap.dedent(
        """
        import rphonenumbers._fallback
        rphonenumbers._fallback._locate = lambda: None  # as if phonenumbers were not installed
        import rphonenumbers
        assert not hasattr(rphonenumbers, "is_emergency_number")
        try:
            rphonenumbers.AsYouTypeFormatter
        except AttributeError as exc:
            print(exc)
        rphonenumbers.install()
        try:
            import phonenumbers.geocoder
        except ImportError as exc:
            print(exc)
        print(rphonenumbers.format_number(rphonenumbers.parse("+442083661177"), 0))
        """
    )
    out = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
    hint = (
        "from the phonenumbers package, which is not installed; "
        'install it with: pip install "rphonenumbers[full]"'
    )
    assert out.stdout.splitlines() == [
        "rphonenumbers takes phonenumbers.AsYouTypeFormatter " + hint,
        "rphonenumbers takes phonenumbers.geocoder " + hint,
        "+442083661177",
    ]


def test_star_import_exports_everything_listed():
    namespace = {}
    exec("from rphonenumbers import *", namespace)
    assert set(pn.__all__) <= set(namespace)


def test_install_aliases_phonenumbers_modules():
    script = textwrap.dedent(
        """
        import rphonenumbers
        rphonenumbers.install()
        import phonenumbers
        from phonenumbers.phonenumberutil import NumberParseException
        from phonenumbers import phonenumber
        assert phonenumbers is rphonenumbers
        assert NumberParseException is rphonenumbers.NumberParseException
        assert phonenumber.PhoneNumber is rphonenumbers.PhoneNumber
        print(phonenumbers.format_number(phonenumbers.parse("+442083661177"), 1))
        """
    )
    out = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
    assert out.stdout.strip() == "+44 20 8366 1177"
