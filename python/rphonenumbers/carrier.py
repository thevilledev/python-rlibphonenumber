"""The carrier a mobile number was originally allocated to.

rlibphonenumber does not implement this, so importing this module returns
``phonenumbers.carrier`` from the phonenumbers package (see ``_fallback``).
Requires ``pip install "rphonenumbers[full]"``.
"""

import sys

# Absolute import: after install() this file also runs as phonenumbers.carrier.
from rphonenumbers import _fallback

sys.modules[__name__] = _fallback.submodule("carrier")
