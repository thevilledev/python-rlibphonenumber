"""Small helpers shared by the data classes.

These mirror the helpers in ``phonenumbers.util`` that user code (and the
``phonenumbers`` doctests) occasionally import directly.
"""

U_EMPTY_STRING = ""
U_PLUS = "+"


def u(s):
    return s


def unicod(s):
    return str(s)


def to_long(value):
    return int(value)


def prnt(*args, **kwargs):
    print(*args, **kwargs)


def force_unicode(s):
    """Return None unchanged, otherwise coerce to str."""
    if s is None:
        return None
    return str(s)


def rpr(s):
    """repr() for strings, rendered the same way as phonenumbers."""
    if s is None:
        return "None"
    seen_unicode = False
    results = []
    for cc in s:
        ccn = ord(cc)
        if 32 <= ccn < 127:
            if cc in ("'", "\\"):
                results.append("\\")
            results.append(cc)
        else:
            seen_unicode = True
            if ccn <= 0xFFFF:
                results.append("\\u%04x" % ccn)
            else:
                results.append("\\U%08x" % ccn)
    result = "'" + "".join(results) + "'"
    if seen_unicode:
        return "u(" + result + ")"
    return result


class UnicodeMixin:
    """Routes ``__str__`` to ``__unicode__``."""

    def __str__(self):
        return self.__unicode__()


class ImmutableMixin:
    """Rejects attribute assignment outside of ``@mutating_method`` calls."""

    _mutable = False

    def __setattr__(self, name, value):
        if self._mutable or name == "_mutable":
            object.__setattr__(self, name, value)
        else:
            raise TypeError("Can't modify immutable instance")

    def __delattr__(self, name):
        if self._mutable:
            object.__delattr__(self, name)
        else:
            raise TypeError("Can't modify immutable instance")


def mutating_method(func):
    """Decorator allowing a method of an ImmutableMixin subclass to mutate."""

    def wrapper(self, *args, **kwargs):
        old_mutable = self._mutable
        self._mutable = True
        try:
            return func(self, *args, **kwargs)
        finally:
            self._mutable = old_mutable

    return wrapper
