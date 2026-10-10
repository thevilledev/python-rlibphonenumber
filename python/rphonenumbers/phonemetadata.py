"""Metadata data classes, API-compatible with ``phonenumbers.phonemetadata``.

Only the user-constructible value classes are implemented: ``NumberFormat``
(the input to ``format_by_pattern``) and ``PhoneNumberDesc``. The native
metadata is not exposed; ``PhoneMetadata`` is phonenumbers' own class, taken
from the phonenumbers package when it is installed (see ``_fallback``).
"""

from . import _fallback
from .util import ImmutableMixin, UnicodeMixin, force_unicode, mutating_method, rpr


class NumberFormat(UnicodeMixin, ImmutableMixin):
    """Representation of way that a phone number can be formatted for output.

    ``format`` uses Python ``re.sub`` replacement syntax (``\\1``), as in
    phonenumbers; it is translated for the native formatter automatically.
    """

    @mutating_method
    def __init__(
        self,
        pattern=None,
        format=None,
        leading_digits_pattern=None,
        national_prefix_formatting_rule=None,
        national_prefix_optional_when_formatting=None,
        domestic_carrier_code_formatting_rule=None,
    ):
        self.pattern = force_unicode(pattern)
        self.format = force_unicode(format)
        self.leading_digits_pattern = []
        if leading_digits_pattern is not None:
            self.leading_digits_pattern = [force_unicode(p) for p in leading_digits_pattern]
        self.national_prefix_formatting_rule = force_unicode(national_prefix_formatting_rule)
        if national_prefix_optional_when_formatting is not None:
            self.national_prefix_optional_when_formatting = bool(national_prefix_optional_when_formatting)
        else:
            self.national_prefix_optional_when_formatting = None
        self.domestic_carrier_code_formatting_rule = force_unicode(domestic_carrier_code_formatting_rule)

    def merge_from(self, other):
        """Merge information from another NumberFormat object into this one."""
        if other.pattern is not None:
            self.pattern = other.pattern
        if other.format is not None:
            self.format = other.format
        self.leading_digits_pattern.extend(other.leading_digits_pattern)
        if other.national_prefix_formatting_rule is not None:
            self.national_prefix_formatting_rule = other.national_prefix_formatting_rule
        if other.national_prefix_optional_when_formatting is not None:
            self.national_prefix_optional_when_formatting = other.national_prefix_optional_when_formatting
        if other.domestic_carrier_code_formatting_rule is not None:
            self.domestic_carrier_code_formatting_rule = other.domestic_carrier_code_formatting_rule

    def __eq__(self, other):
        if not isinstance(other, NumberFormat):
            return False
        return repr(self) == repr(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None

    def __repr__(self):
        return str(self)

    def __unicode__(self):
        result = "NumberFormat(pattern=%s, format=%s" % (rpr(self.pattern), rpr(self.format))
        if self.leading_digits_pattern:
            result += ", leading_digits_pattern=[%s]" % ", ".join(
                rpr(ld) for ld in self.leading_digits_pattern
            )
        if self.national_prefix_formatting_rule is not None:
            result += ", national_prefix_formatting_rule=%s" % rpr(self.national_prefix_formatting_rule)
        if self.national_prefix_optional_when_formatting is not None:
            result += ", national_prefix_optional_when_formatting=%s" % str(
                self.national_prefix_optional_when_formatting
            )
        if self.domestic_carrier_code_formatting_rule is not None:
            result += ", domestic_carrier_code_formatting_rule=%s" % rpr(
                self.domestic_carrier_code_formatting_rule
            )
        result += ")"
        return result


class PhoneNumberDesc(UnicodeMixin, ImmutableMixin):
    """Class representing the description of a set of phone numbers."""

    @mutating_method
    def __init__(
        self,
        national_number_pattern=None,
        example_number=None,
        possible_length=None,
        possible_length_local_only=None,
    ):
        self.national_number_pattern = force_unicode(national_number_pattern)
        self.example_number = force_unicode(example_number)
        self.possible_length = () if possible_length is None else possible_length
        self.possible_length_local_only = (
            () if possible_length_local_only is None else possible_length_local_only
        )

    def merge_from(self, other):
        """Merge information from another PhoneNumberDesc object into this one."""
        if other.national_number_pattern is not None:
            self.national_number_pattern = other.national_number_pattern
        if other.example_number is not None:
            self.example_number = other.example_number

    def __eq__(self, other):
        if not isinstance(other, PhoneNumberDesc):
            return False
        return repr(self) == repr(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None

    def __repr__(self):
        return str(self)

    def __unicode__(self):
        parts = []
        if self.national_number_pattern is not None:
            parts.append("national_number_pattern=%s" % rpr(self.national_number_pattern))
        if self.example_number is not None:
            parts.append("example_number=%s" % rpr(self.example_number))
        if self.possible_length:
            parts.append("possible_length=%s" % (tuple(self.possible_length),))
        if self.possible_length_local_only:
            parts.append("possible_length_local_only=%s" % (tuple(self.possible_length_local_only),))
        return "PhoneNumberDesc(%s)" % ", ".join(parts)


def __getattr__(name):
    if name == "PhoneMetadata":
        return _fallback.attribute("phonenumbers.phonemetadata", name)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
