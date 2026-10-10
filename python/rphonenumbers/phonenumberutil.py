"""Phone number parsing, formatting and validation.

API-compatible with ``phonenumbers.phonenumberutil``. The functions are
implemented natively in ``rphonenumbers._rphonenumbers`` on top of the
rlibphonenumber Rust crate; the lookups that phonenumbers implements as plain
dictionary access are kept in Python, where they are fastest.
"""

import re

from . import _fallback
from . import _rphonenumbers as _native

# Native implementations, exported under their phonenumbers names.
from ._rphonenumbers import (  # noqa: F401
    can_be_internationally_dialled,
    convert_alpha_characters_in_number,
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
    ndd_prefix_for_region,
    normalize_diallable_chars_only,
    normalize_digits_only,
    number_type,
    parse,
    region_code_for_number,
    supported_types_for_non_geo_entity,
    supported_types_for_region,
    truncate_too_long_number,
)
from .util import UnicodeMixin

# The region code used for numbers belonging to non-geographical entities.
REGION_CODE_FOR_NON_GEO_ENTITY = "001"
# The region code returned for unknown country calling codes.
UNKNOWN_REGION = "ZZ"
# Matches runs of non-digit characters.
NON_DIGITS_PATTERN = re.compile("(?:\\D+)")

COUNTRY_CODE_TO_REGION_CODE = _native._country_code_to_region_code()
COUNTRY_CODES_FOR_NON_GEO_REGIONS = _native._non_geo_country_codes()
SUPPORTED_REGIONS = set(_native._region_to_country_code())

_REGION_TO_COUNTRY_CODE = _native._region_to_country_code()
_NANPA_COUNTRY_CODE = 1
_NANPA_REGIONS = frozenset(COUNTRY_CODE_TO_REGION_CODE.get(_NANPA_COUNTRY_CODE, ()))


class PhoneNumberFormat:
    """Phone number format: E164, INTERNATIONAL, NATIONAL or RFC3966."""

    E164 = 0
    INTERNATIONAL = 1
    NATIONAL = 2
    RFC3966 = 3

    @classmethod
    def to_string(cls, val):
        for name in ("E164", "INTERNATIONAL", "NATIONAL", "RFC3966"):
            if val == getattr(cls, name):
                return name
        return "INVALID (%d)" % val


class PhoneNumberType:
    """Type of phone numbers."""

    FIXED_LINE = 0
    MOBILE = 1
    # In some regions (e.g. the USA), it is impossible to distinguish between
    # fixed-line and mobile numbers by looking at the phone number itself.
    FIXED_LINE_OR_MOBILE = 2
    TOLL_FREE = 3
    PREMIUM_RATE = 4
    SHARED_COST = 5
    VOIP = 6
    PERSONAL_NUMBER = 7
    PAGER = 8
    UAN = 9
    VOICEMAIL = 10
    # A phone number is of type UNKNOWN when it does not fit any of the known
    # patterns for a specific region.
    UNKNOWN = 99

    _NAMES = (
        "FIXED_LINE",
        "MOBILE",
        "FIXED_LINE_OR_MOBILE",
        "TOLL_FREE",
        "PREMIUM_RATE",
        "SHARED_COST",
        "VOIP",
        "PERSONAL_NUMBER",
        "PAGER",
        "UAN",
        "VOICEMAIL",
        "UNKNOWN",
    )

    @classmethod
    def values(cls):
        return tuple(getattr(cls, name) for name in cls._NAMES)

    @classmethod
    def to_string(cls, val):
        for name in cls._NAMES:
            if val == getattr(cls, name):
                return name
        return "INVALID (%d)" % val


class MatchType:
    """Types of phone number matches."""

    NOT_A_NUMBER = 0
    NO_MATCH = 1
    SHORT_NSN_MATCH = 2
    NSN_MATCH = 3
    EXACT_MATCH = 4

    @classmethod
    def to_string(cls, val):
        for name in ("NOT_A_NUMBER", "NO_MATCH", "SHORT_NSN_MATCH", "NSN_MATCH", "EXACT_MATCH"):
            if val == getattr(cls, name):
                return name
        return "INVALID (%d)" % val


class ValidationResult:
    """Possible outcomes when testing if a PhoneNumber is a possible number."""

    IS_POSSIBLE = 0
    IS_POSSIBLE_LOCAL_ONLY = 4
    INVALID_COUNTRY_CODE = 1
    TOO_SHORT = 2
    INVALID_LENGTH = 5
    TOO_LONG = 3

    @classmethod
    def to_string(cls, val):
        for name in (
            "IS_POSSIBLE",
            "IS_POSSIBLE_LOCAL_ONLY",
            "INVALID_COUNTRY_CODE",
            "TOO_SHORT",
            "INVALID_LENGTH",
            "TOO_LONG",
        ):
            if val == getattr(cls, name):
                return name
        return "INVALID (%d)" % val


class NumberParseException(UnicodeMixin, Exception):
    """Exception when attempting to parse a putative phone number"""

    # The reason a string could not be interpreted as a phone number.
    INVALID_COUNTRY_CODE = 0
    NOT_A_NUMBER = 1
    TOO_SHORT_AFTER_IDD = 2
    TOO_SHORT_NSN = 3
    TOO_LONG = 4

    def __init__(self, error_type, msg):
        Exception.__init__(self, msg)
        self.error_type = error_type
        self._msg = msg

    def __reduce__(self):
        return (type(self), (self.error_type, self._msg))

    def __unicode__(self):
        return "(%s) %s" % (self.error_type, self._msg)


def supported_calling_codes():
    """Returns all country calling codes the library has metadata for."""
    return set(COUNTRY_CODE_TO_REGION_CODE.keys())


def region_code_for_country_code(country_code):
    """Returns the region code that matches a specific country calling code.

    For non-geographical calling codes this is "001"; for unknown codes it is
    UNKNOWN_REGION ("ZZ").
    """
    regions = COUNTRY_CODE_TO_REGION_CODE.get(country_code, None)
    if regions is None:
        return UNKNOWN_REGION
    return regions[0]


def region_codes_for_country_code(country_code):
    """Returns a tuple of all region codes sharing a country calling code."""
    regions = COUNTRY_CODE_TO_REGION_CODE.get(country_code, None)
    if regions is None:
        return ()
    return regions


def country_code_for_region(region_code):
    """Returns the country calling code for a region, or 0 if it is invalid."""
    if region_code is None or region_code not in SUPPORTED_REGIONS:
        return 0
    return country_code_for_valid_region(region_code)


def country_code_for_valid_region(region_code):
    """Returns the country calling code for a region assumed to be valid.

    Raises Exception if the region is unknown.
    """
    country_code = _REGION_TO_COUNTRY_CODE.get(region_code.upper())
    if country_code is None:
        raise Exception("Invalid region code %s" % region_code)
    return country_code


def is_nanpa_country(region_code):
    """Checks if this region is a NANPA region."""
    return region_code in _NANPA_REGIONS


def national_significant_number(numobj):
    """Gets the national significant number of a phone number.

    Note that a national significant number doesn't contain a national prefix
    or any formatting.
    """
    national_number = ""
    if numobj.italian_leading_zero:
        num_zeros = numobj.number_of_leading_zeros
        if num_zeros is None:
            num_zeros = 1
        if num_zeros > 0:
            national_number = "0" * num_zeros
    national_number += str(numobj.national_number)
    return national_number


def __getattr__(name):
    if name == "PhoneMetadata":
        return _fallback.attribute("phonenumbers.phonenumberutil", name)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
