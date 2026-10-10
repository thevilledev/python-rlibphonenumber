"""The parts of the phonenumbers API that rlibphonenumber does not implement.

Short numbers, as-you-type formatting, raw metadata and the geocoder, carrier
and timezone modules come from the phonenumbers package itself when it is
installed (``pip install "rphonenumbers[full]"``). They run phonenumbers' own
Python code and data, and accept this package's ``PhoneNumber`` objects.

phonenumbers is loaded on first use as a private copy named
``rphonenumbers._phonenumbers``. It cannot be imported under its own name:
``install()`` points ``phonenumbers`` at this package, and phonenumbers loads
its region metadata lazily through relative imports that would then resolve to
this package instead of itself.
"""

import importlib
import importlib.util
import sys
import threading
from importlib.machinery import PathFinder

_PRIVATE_NAME = "rphonenumbers._phonenumbers"

_lock = threading.Lock()
_package = None


def _locate():
    """Find the installed phonenumbers package without importing it.

    Searches sys.path directly: ``importlib.util.find_spec`` would return this
    package once ``install()`` has aliased it.
    """
    return PathFinder.find_spec("phonenumbers")


def _missing(feature):
    return ImportError(
        "rphonenumbers takes %s from the phonenumbers package, which is not installed; "
        'install it with: pip install "rphonenumbers[full]"' % feature
    )


def upstream(feature):
    """Return the private copy of phonenumbers, loading it on first use.

    ``feature`` names what the caller needs, for the error message raised when
    phonenumbers is not installed.
    """
    global _package
    with _lock:
        if _package is None:
            spec = _locate()
            if spec is None or not spec.submodule_search_locations:
                raise _missing(feature)
            private = importlib.util.spec_from_file_location(
                _PRIVATE_NAME, spec.origin, submodule_search_locations=list(spec.submodule_search_locations)
            )
            module = importlib.util.module_from_spec(private)
            sys.modules[_PRIVATE_NAME] = module
            try:
                private.loader.exec_module(module)
            except BaseException:
                for name in list(sys.modules):
                    if name == _PRIVATE_NAME or name.startswith(_PRIVATE_NAME + "."):
                        del sys.modules[name]
                raise
            _package = module
        return _package


def attribute(module, name):
    """Return ``phonenumbers.<module>.<name>``, raising AttributeError if unavailable."""
    qualified = "%s.%s" % (module, name)
    try:
        package = upstream(qualified)
    except ImportError as exc:
        raise AttributeError(str(exc)) from None
    source = package if module == "phonenumbers" else getattr(package, module.rpartition(".")[2])
    return getattr(source, name)


def submodule(name):
    """Return the ``phonenumbers.<name>`` module."""
    upstream("phonenumbers." + name)
    try:
        return importlib.import_module("%s.%s" % (_PRIVATE_NAME, name))
    except ModuleNotFoundError as exc:
        if exc.name is None or not exc.name.startswith(_PRIVATE_NAME):
            raise
        raise ImportError(
            "the installed phonenumbers package has no %s module; phonenumberslite leaves out "
            "geocoding, carrier and timezone data, install phonenumbers instead" % name
        ) from exc
