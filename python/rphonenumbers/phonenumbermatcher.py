"""Finding phone numbers in text, API-compatible with ``phonenumbers.phonenumbermatcher``."""

from . import _rphonenumbers as _native
from .util import UnicodeMixin


class Leniency:
    """Leniency when finding potential phone numbers in text segments.

    The levels here are ordered in increasing strictness.
    """

    POSSIBLE = 0
    VALID = 1
    STRICT_GROUPING = 2
    EXACT_GROUPING = 3


class PhoneNumberMatcher:
    """A stateful class that finds and extracts telephone numbers from text.

    The native matcher scans the whole text on the first call to
    ``has_next()``; matches are then handed out one at a time.
    """

    # The potential states of a PhoneNumberMatcher.
    _NOT_READY = 0
    _READY = 1
    _DONE = 2

    def __init__(self, text, region, leniency=Leniency.VALID, max_tries=65535, min_candidate_length=1):
        if leniency is None:
            raise ValueError("Need a leniency value")
        if int(max_tries) < 0:
            raise ValueError("Need max_tries to be positive int")
        self.text = text
        if self.text is None:
            self.text = ""
        self.preferred_region = region
        self.leniency = leniency
        self._max_tries = int(max_tries)
        self._min_candidate_length = int(min_candidate_length)
        self._state = PhoneNumberMatcher._NOT_READY
        self._last_match = None
        self._pending = None

    def _matches(self):
        if self._pending is None:
            found = _native._find_numbers(self.text, self.preferred_region, self.leniency, self._max_tries)
            # Python-specific option (not in libphonenumber): skip candidates
            # shorter than min_candidate_length.
            self._pending = [
                PhoneNumberMatch(start, raw, numobj)
                for start, raw, numobj in reversed(found)
                if len(raw) >= self._min_candidate_length
            ]
        return self._pending

    def has_next(self):
        """Indicates whether there is another match available"""
        if self._state == PhoneNumberMatcher._NOT_READY:
            pending = self._matches()
            if pending:
                self._last_match = pending.pop()
                self._state = PhoneNumberMatcher._READY
            else:
                self._state = PhoneNumberMatcher._DONE
        return self._state == PhoneNumberMatcher._READY

    def next(self):
        """Return the next match; raises Exception if no next match available"""
        if not self.has_next():
            raise StopIteration("No next match")
        result = self._last_match
        self._last_match = None
        self._state = PhoneNumberMatcher._NOT_READY
        return result

    def __iter__(self):
        while self.has_next():
            yield self.next()


class PhoneNumberMatch(UnicodeMixin):
    """The immutable match of a phone number within a piece of text.

    A match consists of the phone number (in .number) as well as the .start
    and .end offsets of the corresponding subsequence of the searched text.
    Use .raw_string to obtain a copy of the matched subsequence.
    """

    def __init__(self, start, raw_string, numobj):
        if start < 0:
            raise Exception("Start index not >= 0")
        if raw_string is None or numobj is None:
            raise Exception("Invalid argument")
        self.start = start
        self.raw_string = raw_string
        self.end = self.start + len(raw_string)
        self.number = numobj

    def __eq__(self, other):
        if not isinstance(other, PhoneNumberMatch):
            return False
        return (
            self.start == other.start
            and self.raw_string == other.raw_string
            and self.end == other.end
            and self.number == other.number
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = None

    def __repr__(self):
        return "PhoneNumberMatch(start=%r, raw_string=%r, numobj=%r)" % (
            self.start,
            self.raw_string,
            self.number,
        )

    def __unicode__(self):
        return "PhoneNumberMatch [%s,%s) %s" % (self.start, self.end, self.raw_string)
