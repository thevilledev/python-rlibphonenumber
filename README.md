# rphonenumbers

[![PyPI](https://img.shields.io/pypi/v/rphonenumbers)](https://pypi.org/project/rphonenumbers/)
[![Python versions](https://img.shields.io/pypi/pyversions/rphonenumbers)](https://pypi.org/project/rphonenumbers/)
[![CI](https://github.com/thevilledev/python-rlibphonenumber/actions/workflows/ci.yml/badge.svg)](https://github.com/thevilledev/python-rlibphonenumber/actions/workflows/ci.yml)

A drop-in replacement for [`phonenumbers`](https://github.com/daviddrysdale/python-phonenumbers)
that runs parsing, formatting, validation and number matching on
[rlibphonenumber](https://github.com/vloldik/rlibphonenumber), a Rust port of Google's
libphonenumber. Same functions, same signatures, same results; parsing and validation run 9–16x
faster, and mixed-region batches up to 75x faster.

rlibphonenumber does not cover all of `phonenumbers`: short numbers, as-you-type formatting, raw
metadata and the geocoder, carrier and timezone modules are missing. With the `full` extra,
rphonenumbers takes those from `phonenumbers` itself, so the whole API is available.

> **Status: alpha.** Verified against `phonenumbers` 9.0.41.

## Installation

```bash
pip install rphonenumbers           # the Rust-backed core API
pip install "rphonenumbers[full]"   # plus the rest of the phonenumbers API
```

Wheels are published for CPython 3.10+ and free-threaded CPython 3.14t on:

- Linux x86_64 and aarch64 (glibc 2.17+ and musl 1.2+)
- macOS x86_64 (10.12+) and arm64 (11.0+)
- Windows x64 and ARM64

On other platforms pip builds from the source distribution, which needs a Rust toolchain (1.88+).

## Usage

Import it in place of `phonenumbers`:

```python
import rphonenumbers as phonenumbers

x = phonenumbers.parse("020 8366 1177", "GB")
phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.E164)  # '+442083661177'
phonenumbers.is_valid_number(x)  # True
```

Or make every `import phonenumbers` in the process resolve to it, including imports inside
third-party libraries such as `django-phonenumber-field`:

```python
import rphonenumbers
rphonenumbers.install()  # call before those libraries are imported

import phonenumbers  # -> rphonenumbers
```

The two packages can be installed side by side; nothing is shadowed unless you call `install()`.

Libraries can use parts of the API that rlibphonenumber lacks. For example,
django-phonenumber-field's `validate_phonenumber` validator calls `is_valid_short_number`, so
install `rphonenumbers[full]` if you use it.

## Performance

Speedup over `phonenumbers` 9.0.41 from `python benches/bench.py`, with CPython 3.14.8:

| Operation | Apple M1 Max | AMD Ryzen AI 9 HX PRO 370 |
|---|---:|---:|
| `parse("+1 650-253-0000")` | 10.3x | 9.0x |
| `parse("020 8366 1177", "GB")` | 13.1x | 11.5x |
| `format_number(E164)` | 1.1x | 1.1x |
| `format_number(INTERNATIONAL)` | 5.5x | 5.1x |
| `is_valid_number` | 16.4x | 14.6x |
| `number_type` | 15.9x | 13.9x |
| parse + validate + E164, 489 numbers across all regions | 63.1x | 75.2x |
| `PhoneNumberMatcher`, 944 chars | 11.2x | 13.1x |

E164 formatting is already a string concatenation in `phonenumbers`, so there is nothing to win
there. See [Performance](https://github.com/thevilledev/python-rlibphonenumber/blob/main/docs/performance.md)
for the timings and how they were measured.

## Compatibility

`phonenumbers.phonenumberutil`'s public API, the `PhoneNumber` data classes and
`PhoneNumberMatcher` run in Rust. The short-number API, `AsYouTypeFormatter`, `PhoneMetadata` and
the geocoder, carrier and timezone modules come from `phonenumbers` when it is installed
(`rphonenumbers[full]`), at `phonenumbers`' own speed.

A differential test suite compares every public function against `phonenumbers` over about 6.7
million inputs. [Compatibility](https://github.com/thevilledev/python-rlibphonenumber/blob/main/docs/compatibility.md)
lists what runs where, the known differences, and the rlibphonenumber bugs this package works
around.

## Development

See [Development](https://github.com/thevilledev/python-rlibphonenumber/blob/main/docs/development.md)
for building from source and running the tests and benchmarks, and
[RELEASING.md](https://github.com/thevilledev/python-rlibphonenumber/blob/main/RELEASING.md)
for how releases are published.

## License

Apache-2.0. See
[NOTICE](https://github.com/thevilledev/python-rlibphonenumber/blob/main/NOTICE) for
attributions: the metadata and algorithms come from Google's libphonenumber via rlibphonenumber,
and the Python API mirrors python-phonenumbers.
