"""Geographical descriptions of phone numbers.

rlibphonenumber does not implement this, so importing this module returns
``phonenumbers.geocoder`` from the phonenumbers package (see ``_fallback``).
Requires ``pip install "rphonenumbers[full]"``.
"""

import sys

# Absolute import: after install() this file also runs as phonenumbers.geocoder.
from rphonenumbers import _fallback

sys.modules[__name__] = _fallback.submodule("geocoder")
