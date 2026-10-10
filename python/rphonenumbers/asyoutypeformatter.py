"""Formatting a phone number as it is typed (``AsYouTypeFormatter``).

rlibphonenumber does not implement this, so importing this module returns
``phonenumbers.asyoutypeformatter`` from the phonenumbers package (see ``_fallback``).
Requires ``pip install "rphonenumbers[full]"``.
"""

import sys

# Absolute import: after install() this file also runs as phonenumbers.asyoutypeformatter.
from rphonenumbers import _fallback

sys.modules[__name__] = _fallback.submodule("asyoutypeformatter")
