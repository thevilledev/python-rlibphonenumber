"""Short numbers: emergency numbers, short codes and their cost.

rlibphonenumber does not implement this, so importing this module returns
``phonenumbers.shortnumberinfo`` from the phonenumbers package (see ``_fallback``).
Requires ``pip install "rphonenumbers[full]"``.
"""

import sys

# Absolute import: after install() this file also runs as phonenumbers.shortnumberinfo.
from rphonenumbers import _fallback

sys.modules[__name__] = _fallback.submodule("shortnumberinfo")
