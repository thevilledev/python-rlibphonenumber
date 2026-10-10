# rphonenumbers

[![PyPI](https://img.shields.io/pypi/v/rphonenumbers)](https://pypi.org/project/rphonenumbers/)
[![Python versions](https://img.shields.io/pypi/pyversions/rphonenumbers)](https://pypi.org/project/rphonenumbers/)
[![CI](https://github.com/thevilledev/python-rlibphonenumber/actions/workflows/ci.yml/badge.svg)](https://github.com/thevilledev/python-rlibphonenumber/actions/workflows/ci.yml)

A drop-in replacement for [`phonenumbers`](https://github.com/daviddrysdale/python-phonenumbers)
that runs parsing, formatting, validation and number matching on
[rlibphonenumber](https://github.com/vloldik/rlibphonenumber), a Rust port of Google's
libphonenumber. Same functions, same signatures, same results, typically 10–70x faster.

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

`python benches/bench.py` on an Apple M1 Max, CPython 3.14, `phonenumbers` 9.0.41:

| Operation | phonenumbers | rphonenumbers | Speedup |
|---|---:|---:|---:|
| `parse("+1 650-253-0000")` | 9.08 µs | 817 ns | 11.1x |
| `parse("020 8366 1177", "GB")` | 11.65 µs | 822 ns | 14.2x |
| `format_number(E164)` | 270 ns | 248 ns | 1.1x |
| `format_number(INTERNATIONAL)` | 3.97 µs | 680 ns | 5.8x |
| `is_valid_number` | 8.98 µs | 511 ns | 17.6x |
| `number_type` | 8.75 µs | 507 ns | 17.3x |
| parse + validate + E164, 489 numbers across all regions | 69.7 ms | 998 µs | 69.8x |
| `PhoneNumberMatcher`, 944 chars | 953 µs | 79 µs | 12.1x |

E164 formatting is already a string concatenation in `phonenumbers`, so there is nothing to win
there. The mixed-region batch gains the most because `phonenumbers` recompiles regexes once
Python's `re` cache (512 entries) overflows.

## Compatibility

Implemented in Rust:

- Everything in `phonenumbers.phonenumberutil`'s public API: `parse`, all `format_*` functions,
  validation, number types, matching, example numbers, region and calling-code queries,
  `COUNTRY_CODE_TO_REGION_CODE`, `SUPPORTED_REGIONS`, and so on.
- `PhoneNumber`, `FrozenPhoneNumber`, `CountryCodeSource`, `NumberFormat` and `PhoneNumberDesc`.
- `PhoneNumberMatcher`, `PhoneNumberMatch` and `Leniency`.

The functions accept any object with `PhoneNumber`'s attributes, including upstream
`phonenumbers.PhoneNumber` instances.

Taken from `phonenumbers` when it is installed (`rphonenumbers[full]`), because the
rlibphonenumber crate does not provide them:

- The short-number API (`is_valid_short_number`, `expected_cost`, `is_emergency_number`, ...).
- `AsYouTypeFormatter` and `PhoneMetadata`.
- The `geocoder`, `carrier` and `timezone` modules.

These run `phonenumbers`' own Python code and data, so they are no faster than in `phonenumbers`,
and they accept rphonenumbers' `PhoneNumber` objects. `phonenumbers` is loaded as a private copy
on first use, so this also works after `install()`. Without it, using these raises
`AttributeError` or `ImportError` explaining what to install.

A [differential test suite](https://github.com/thevilledev/python-rlibphonenumber/blob/main/tests/differential.py)
checks every public function against `phonenumbers`: about 6.7 million comparisons over the example
numbers of every region in many textual variants (national, international, IDD-prefixed, with
extensions, truncated, padded, shuffled), hand-written edge cases (RFC 3966 URIs, alpha numbers,
full-width and Arabic-Indic digits, invalid regions, oversized input), and every region and
calling code. Results, raised exception types and `NumberParseException` messages must all be
identical.

### Known differences

- `example_number(None)` returns a valid fixed-line example, but not necessarily the one
  `phonenumbers` picks: upstream returns the first hit while iterating a `set`, so its answer
  depends on `PYTHONHASHSEED`.
- `format_out_of_country_keeping_alpha_chars(numobj, None)` returns the international format;
  `phonenumbers` raises `AttributeError` when the number has `raw_input`.
- `PhoneNumberMatcher` scans the whole text on the first `has_next()` call rather than lazily;
  the sequence of matches is the same. `min_candidate_length` filters on the matched string.
- `parse(..., _check_region=False)` (a private parameter) is accepted but ignored.
- `NumberFormat` patterns passed to `format_by_pattern` run on Rust's `regex` engine, so
  Python-only syntax such as lookaround is rejected with `re.error`.
- The APIs taken from `phonenumbers` use the metadata of the installed `phonenumbers` release.
  When it differs from `rphonenumbers.__phonenumbers_version__`, their results can disagree with
  the core API on recently changed numbers.

### Upstream fixes

rlibphonenumber 2.2.14 has three bugs that make its results differ from libphonenumber. This
package corrects them itself until the fixes are released upstream:

- `is_valid_number_for_region` does not check that the number's country code belongs to the
  region, so `+44 2423232345` is reported valid for `BS`
  ([vloldik/rlibphonenumber#35](https://github.com/vloldik/rlibphonenumber/pull/35)).
- `format_by_pattern` renders RFC 3966 extensions in national style (`" ext. 42"`) instead of
  `";ext=42"` ([vloldik/rlibphonenumber#36](https://github.com/vloldik/rlibphonenumber/pull/36)).
  rlibphonenumber inherits this from libphonenumber's C++ implementation, fixed there in
  [google/libphonenumber#4087](https://github.com/google/libphonenumber/pull/4087).
- `format_out_of_country_keeping_alpha_chars` emits `" 247 40123"` instead of `"+247 40123"`
  when the calling region has no single or preferred international prefix
  ([vloldik/rlibphonenumber#37](https://github.com/vloldik/rlibphonenumber/pull/37)).

## Development

Requires a Rust toolchain (1.88+):

```bash
pip install maturin
maturin develop --release
pip install pytest phonenumbers==9.0.41
pytest                         # API tests + differential tests against phonenumbers
python tests/differential.py   # differential summary, per function
python benches/bench.py
```

The `phonenumbers` version used for testing must match the libphonenumber metadata release
bundled in rlibphonenumber (`rphonenumbers.__phonenumbers_version__`).

See [RELEASING.md](https://github.com/thevilledev/python-rlibphonenumber/blob/main/RELEASING.md)
for how releases are published.

## License

Apache-2.0. See
[NOTICE](https://github.com/thevilledev/python-rlibphonenumber/blob/main/NOTICE) for
attributions: the metadata and algorithms come from Google's libphonenumber via rlibphonenumber,
and the Python API mirrors python-phonenumbers.
