"""Time zones of phone numbers.

rlibphonenumber does not implement this, so importing this module returns
``phonenumbers.timezone`` from the phonenumbers package (see ``_fallback``).
Requires ``pip install "rphonenumbers[full]"``.
"""

import sys

# Absolute import: after install() this file also runs as phonenumbers.timezone.
from rphonenumbers import _fallback

sys.modules[__name__] = _fallback.submodule("timezone")
