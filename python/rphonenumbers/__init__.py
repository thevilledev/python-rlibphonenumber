"""Drop-in replacement for the ``phonenumbers`` package, backed by Rust.

Use it under its own name::

    import rphonenumbers as phonenumbers

or make every ``import phonenumbers`` in the process (including inside
third-party libraries) resolve to it::

    import rphonenumbers
    rphonenumbers.install()

>>> import rphonenumbers as phonenumbers
>>> x = phonenumbers.parse("+442083661177", None)
>>> print(x)
Country Code: 44 National Number: 2083661177
>>> phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.NATIONAL)
'020 8366 1177'
>>> phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.E164)
'+442083661177'
>>> x == phonenumbers.parse("020 8366 1177", "GB")
True
"""

import sys

from . import _fallback
from ._rphonenumbers import __version__  # noqa: F401
from .phonemetadata import NumberFormat, PhoneNumberDesc
from .phonenumber import CountryCodeSource, FrozenPhoneNumber, PhoneNumber
from .phonenumbermatcher import Leniency, PhoneNumberMatch, PhoneNumberMatcher
from .phonenumberutil import (
    COUNTRY_CODE_TO_REGION_CODE,
    COUNTRY_CODES_FOR_NON_GEO_REGIONS,
    NON_DIGITS_PATTERN,
    REGION_CODE_FOR_NON_GEO_ENTITY,
    SUPPORTED_REGIONS,
    UNKNOWN_REGION,
    MatchType,
    NumberParseException,
    PhoneNumberFormat,
    PhoneNumberType,
    ValidationResult,
    can_be_internationally_dialled,
    convert_alpha_characters_in_number,
    country_code_for_region,
    country_code_for_valid_region,
    country_mobile_token,
    example_number,
    example_number_for_non_geo_entity,
    example_number_for_type,
    format_by_pattern,
    format_in_original_format,
    format_national_number_with_carrier_code,
    format_national_number_with_preferred_carrier_code,
    format_number,
    format_number_for_mobile_dialing,
    format_out_of_country_calling_number,
    format_out_of_country_keeping_alpha_chars,
    invalid_example_number,
    is_alpha_number,
    is_mobile_number_portable_region,
    is_nanpa_country,
    is_number_geographical,
    is_number_match,
    is_number_type_geographical,
    is_possible_number,
    is_possible_number_for_type,
    is_possible_number_for_type_with_reason,
    is_possible_number_string,
    is_possible_number_with_reason,
    is_valid_number,
    is_valid_number_for_region,
    length_of_geographical_area_code,
    length_of_national_destination_code,
    national_significant_number,
    ndd_prefix_for_region,
    normalize_diallable_chars_only,
    normalize_digits_only,
    number_type,
    parse,
    region_code_for_country_code,
    region_code_for_number,
    region_codes_for_country_code,
    supported_calling_codes,
    supported_types_for_non_geo_entity,
    supported_types_for_region,
    truncate_too_long_number,
)

# The libphonenumber metadata release (and phonenumbers version) this build
# matches.
__phonenumbers_version__ = "9.0.41"

__all__ = [
    "PhoneNumber",
    "CountryCodeSource",
    "FrozenPhoneNumber",
    "REGION_CODE_FOR_NON_GEO_ENTITY",
    "NumberFormat",
    "PhoneNumberDesc",
    # items from phonenumberutil.py
    "COUNTRY_CODE_TO_REGION_CODE",
    "SUPPORTED_REGIONS",
    "UNKNOWN_REGION",
    "COUNTRY_CODES_FOR_NON_GEO_REGIONS",
    "NON_DIGITS_PATTERN",
    "MatchType",
    "NumberParseException",
    "PhoneNumberFormat",
    "PhoneNumberType",
    "ValidationResult",
    "can_be_internationally_dialled",
    "convert_alpha_characters_in_number",
    "country_code_for_region",
    "country_code_for_valid_region",
    "country_mobile_token",
    "example_number",
    "example_number_for_type",
    "example_number_for_non_geo_entity",
    "format_by_pattern",
    "format_in_original_format",
    "format_national_number_with_carrier_code",
    "format_national_number_with_preferred_carrier_code",
    "format_number_for_mobile_dialing",
    "format_number",
    "format_out_of_country_calling_number",
    "format_out_of_country_keeping_alpha_chars",
    "invalid_example_number",
    "is_alpha_number",
    "is_nanpa_country",
    "is_number_geographical",
    "is_number_type_geographical",
    "is_number_match",
    "is_possible_number",
    "is_possible_number_for_type",
    "is_possible_number_for_type_with_reason",
    "is_possible_number_string",
    "is_possible_number_with_reason",
    "is_valid_number",
    "is_valid_number_for_region",
    "length_of_geographical_area_code",
    "length_of_national_destination_code",
    "national_significant_number",
    "ndd_prefix_for_region",
    "normalize_digits_only",
    "normalize_diallable_chars_only",
    "number_type",
    "parse",
    "region_code_for_country_code",
    "region_codes_for_country_code",
    "region_code_for_number",
    "supported_calling_codes",
    "supported_types_for_region",
    "supported_types_for_non_geo_entity",
    "truncate_too_long_number",
    "is_mobile_number_portable_region",
    # end of items from phonenumberutil.py
    "PhoneNumberMatch",
    "PhoneNumberMatcher",
    "Leniency",
]

# Public phonenumbers names that rlibphonenumber does not implement. They are
# taken from the phonenumbers package on first access (see _fallback), and
# raise AttributeError with an explanation when it is not installed.
_DELEGATED = frozenset(
    {
        "AsYouTypeFormatter",
        "PhoneMetadata",
        "SUPPORTED_SHORT_REGIONS",
        "ShortNumberCost",
        "is_possible_short_number_for_region",
        "is_possible_short_number",
        "is_valid_short_number_for_region",
        "is_valid_short_number",
        "expected_cost_for_region",
        "expected_cost",
        "connects_to_emergency_number",
        "is_emergency_number",
        "is_carrier_specific",
        "is_carrier_specific_for_region",
        "is_sms_service_for_region",
    }
)


def __getattr__(name):
    if name in _DELEGATED:
        value = _fallback.attribute("phonenumbers", name)
        globals()[name] = value
        return value
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


_SUBMODULES = ("phonenumber", "phonenumberutil", "phonenumbermatcher", "phonemetadata", "util")


def install():
    """Make ``import phonenumbers`` resolve to this package.

    Registers this package and its submodules in ``sys.modules`` under the
    ``phonenumbers`` names, so libraries that import ``phonenumbers`` (for
    example django-phonenumber-field) use the Rust implementation without code
    changes. Call it before those libraries are imported; modules that already
    hold a reference to the original package keep using it.
    """
    package = sys.modules[__name__]
    sys.modules["phonenumbers"] = package
    for name in _SUBMODULES:
        sys.modules["phonenumbers." + name] = sys.modules[__name__ + "." + name]
