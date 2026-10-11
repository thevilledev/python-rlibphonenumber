# Compatibility

rphonenumbers mirrors the public API of `phonenumbers` 9.0.41. Most of it runs in Rust; the parts
that rlibphonenumber does not implement are taken from `phonenumbers` itself.

## Implemented in Rust

- Everything in `phonenumbers.phonenumberutil`'s public API: `parse`, all `format_*` functions,
  validation, number types, matching, example numbers, region and calling-code queries,
  `COUNTRY_CODE_TO_REGION_CODE`, `SUPPORTED_REGIONS`, and so on.
- `PhoneNumber`, `FrozenPhoneNumber`, `CountryCodeSource`, `NumberFormat` and `PhoneNumberDesc`.
- `PhoneNumberMatcher`, `PhoneNumberMatch` and `Leniency`.

The functions accept any object with `PhoneNumber`'s attributes, including upstream
`phonenumbers.PhoneNumber` instances.

## Taken from phonenumbers

These are taken from `phonenumbers` when it is installed (`rphonenumbers[full]`), because the
rlibphonenumber crate does not provide them:

- The short-number API (`is_valid_short_number`, `expected_cost`, `is_emergency_number`, ...).
- `AsYouTypeFormatter` and `PhoneMetadata`.
- The `geocoder`, `carrier` and `timezone` modules.

These run `phonenumbers`' own Python code and data, so they are no faster than in `phonenumbers`,
and they accept rphonenumbers' `PhoneNumber` objects. `phonenumbers` is loaded as a private copy
on first use, so this also works after `install()`. Without it, using these raises
`AttributeError` or `ImportError` explaining what to install.

## How compatibility is checked

A [differential test suite](../tests/differential.py) checks every public function against
`phonenumbers`: about 6.7 million comparisons over the example numbers of every region in many
textual variants (national, international, IDD-prefixed, with extensions, truncated, padded,
shuffled), hand-written edge cases (RFC 3966 URIs, alpha numbers, full-width and Arabic-Indic
digits, invalid regions, oversized input), and every region and calling code. Results, raised
exception types and `NumberParseException` messages must all be identical.

## Known differences

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

## Upstream fixes

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
