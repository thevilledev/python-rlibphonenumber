"""PhoneNumber data class, API-compatible with ``phonenumbers.phonenumber``."""

from .util import ImmutableMixin, UnicodeMixin, force_unicode, mutating_method, rpr, to_long


class CountryCodeSource:
    """Where the country calling code of a parsed number came from."""

    UNSPECIFIED = 0
    FROM_NUMBER_WITH_PLUS_SIGN = 1
    FROM_NUMBER_WITH_IDD = 5
    FROM_NUMBER_WITHOUT_PLUS_SIGN = 10
    FROM_DEFAULT_COUNTRY = 20

    @classmethod
    def to_string(cls, val):
        for name in (
            "UNSPECIFIED",
            "FROM_NUMBER_WITH_PLUS_SIGN",
            "FROM_NUMBER_WITH_IDD",
            "FROM_NUMBER_WITHOUT_PLUS_SIGN",
            "FROM_DEFAULT_COUNTRY",
        ):
            if val == getattr(cls, name):
                return name
        return "INVALID (%d)" % val


class PhoneNumber(UnicodeMixin):
    """A parsed international phone number.

    Instances returned by this library are created natively; the constructor
    below is for user code building numbers by hand.
    """

    def __init__(
        self,
        country_code=None,
        national_number=None,
        extension=None,
        italian_leading_zero=None,
        number_of_leading_zeros=None,
        raw_input=None,
        country_code_source=CountryCodeSource.UNSPECIFIED,
        preferred_domestic_carrier_code=None,
    ):
        self.country_code = None if country_code is None else int(country_code)
        self.national_number = None if national_number is None else to_long(national_number)
        self.extension = force_unicode(extension)
        self.italian_leading_zero = None if italian_leading_zero is None else bool(italian_leading_zero)
        self.number_of_leading_zeros = (
            None if number_of_leading_zeros is None else int(number_of_leading_zeros)
        )
        self.raw_input = force_unicode(raw_input)
        if country_code_source is None:
            country_code_source = CountryCodeSource.UNSPECIFIED
        self.country_code_source = country_code_source
        self.preferred_domestic_carrier_code = force_unicode(preferred_domestic_carrier_code)

    def clear(self):
        """Erase the contents of the object"""
        self.country_code = None
        self.national_number = None
        self.extension = None
        self.italian_leading_zero = None
        self.number_of_leading_zeros = None
        self.raw_input = None
        self.country_code_source = CountryCodeSource.UNSPECIFIED
        self.preferred_domestic_carrier_code = None

    def merge_from(self, other):
        """Merge information from another PhoneNumber object into this one."""
        if other.country_code is not None:
            self.country_code = other.country_code
        if other.national_number is not None:
            self.national_number = other.national_number
        if other.extension is not None:
            self.extension = other.extension
        if other.italian_leading_zero is not None:
            self.italian_leading_zero = other.italian_leading_zero
        if other.number_of_leading_zeros is not None:
            self.number_of_leading_zeros = other.number_of_leading_zeros
        if other.raw_input is not None:
            self.raw_input = other.raw_input
        if other.country_code_source is not CountryCodeSource.UNSPECIFIED:
            self.country_code_source = other.country_code_source
        if other.preferred_domestic_carrier_code is not None:
            self.preferred_domestic_carrier_code = other.preferred_domestic_carrier_code

    def __eq__(self, other):
        if not isinstance(other, PhoneNumber):
            return False
        return (
            self.country_code == other.country_code
            and self.national_number == other.national_number
            and self.extension == other.extension
            and bool(self.italian_leading_zero) == bool(other.italian_leading_zero)
            and self.number_of_leading_zeros == other.number_of_leading_zeros
            and self.raw_input == other.raw_input
            and self.country_code_source == other.country_code_source
            and self.preferred_domestic_carrier_code == other.preferred_domestic_carrier_code
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    # Defining __eq__ disables hashing, exactly as in phonenumbers; use
    # FrozenPhoneNumber for a hashable variant.
    __hash__ = None

    def __repr__(self):
        return (
            "%s(country_code=%s, national_number=%s, extension=%s, "
            "italian_leading_zero=%s, number_of_leading_zeros=%s, "
            "country_code_source=%s, preferred_domestic_carrier_code=%s)"
        ) % (
            type(self).__name__,
            self.country_code,
            self.national_number,
            rpr(self.extension),
            self.italian_leading_zero,
            self.number_of_leading_zeros,
            self.country_code_source,
            rpr(self.preferred_domestic_carrier_code),
        )

    def __unicode__(self):
        result = "Country Code: %s National Number: %s" % (
            self.country_code,
            self.national_number,
        )
        if self.italian_leading_zero is not None:
            result += " Leading Zero(s): %s" % self.italian_leading_zero
        if self.number_of_leading_zeros is not None:
            result += " Number of leading zeros: %d" % self.number_of_leading_zeros
        if self.extension is not None:
            result += " Extension: %s" % self.extension
        if self.country_code_source is not CountryCodeSource.UNSPECIFIED:
            result += " Country Code Source: %s" % self.country_code_source
        if self.preferred_domestic_carrier_code is not None:
            result += " Preferred Domestic Carrier Code: %s" % self.preferred_domestic_carrier_code
        return result


class FrozenPhoneNumber(PhoneNumber, ImmutableMixin):
    """Immutable, hashable version of PhoneNumber"""

    def __hash__(self):
        return hash(
            (
                self.country_code,
                self.national_number,
                self.extension,
                bool(self.italian_leading_zero),
                self.number_of_leading_zeros,
                self.raw_input,
                self.country_code_source,
                self.preferred_domestic_carrier_code,
            )
        )

    @mutating_method
    def __init__(self, *args, **kwargs):
        if len(kwargs) == 0 and len(args) == 1 and isinstance(args[0], PhoneNumber):
            super().__init__(**args[0].__dict__)
        else:
            super().__init__(*args, **kwargs)
