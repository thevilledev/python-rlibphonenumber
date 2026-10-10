"""The private copy of the phonenumbers package that ``_fallback`` loads.

Objects from the delegated APIs (an ``AsYouTypeFormatter``, ``PhoneMetadata``)
belong to modules under this name. Importing it, as unpickling them in a fresh
process does, loads the copy on demand.
"""

import sys

from rphonenumbers import _fallback

sys.modules[__name__] = _fallback.upstream("phonenumbers")
