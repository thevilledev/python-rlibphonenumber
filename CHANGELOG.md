# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-11

First release.

### Added

- Drop-in replacement for the public `phonenumbers.phonenumberutil` API: `parse`, every
  `format_*` function, validation, number types, number matching, example numbers, and region and
  calling-code queries. Results, exception types and `NumberParseException` messages match
  `phonenumbers` 9.0.41, which uses the same libphonenumber metadata as rlibphonenumber 2.2.14.
- `PhoneNumber`, `FrozenPhoneNumber`, `CountryCodeSource`, `NumberFormat` and `PhoneNumberDesc`.
- `PhoneNumberMatcher`, `PhoneNumberMatch` and `Leniency` for finding numbers in text.
- `rphonenumbers.install()`, which makes `import phonenumbers` resolve to this package,
  including imports inside third-party libraries.
- The parts of the API that rlibphonenumber does not implement (the short-number API,
  `AsYouTypeFormatter`, `PhoneMetadata`, and the `geocoder`, `carrier` and `timezone` modules)
  are taken from the `phonenumbers` package when it is installed, for example with
  `pip install "rphonenumbers[full]"`. Without it, using them raises an `AttributeError` or
  `ImportError` that says what to install.
- Workarounds for three rlibphonenumber 2.2.14 bugs, until the upstream fixes are released:
  - `is_valid_number_for_region` now checks that the number's country code belongs to the region
    ([vloldik/rlibphonenumber#35](https://github.com/vloldik/rlibphonenumber/pull/35)).
  - `format_by_pattern` now uses `;ext=` for RFC 3966 extensions
    ([vloldik/rlibphonenumber#36](https://github.com/vloldik/rlibphonenumber/pull/36)).
  - `format_out_of_country_keeping_alpha_chars` now falls back to `+` when the calling region
    has no preferred international prefix
    ([vloldik/rlibphonenumber#37](https://github.com/vloldik/rlibphonenumber/pull/37)).
- Wheels for CPython 3.10+ (abi3) and free-threaded CPython 3.14t on Linux (manylinux and
  musllinux, x86_64 and aarch64), macOS (x86_64 and arm64) and Windows (x64 and ARM64).

[Unreleased]: https://github.com/thevilledev/python-rlibphonenumber/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/thevilledev/python-rlibphonenumber/releases/tag/v0.1.0
