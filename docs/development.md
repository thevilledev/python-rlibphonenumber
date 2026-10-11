# Development

Requires a Rust toolchain (1.88+).

## Building and testing

```bash
pip install maturin
maturin develop --release
pip install pytest phonenumbers==9.0.41
pytest                         # API tests + differential tests against phonenumbers
python tests/differential.py   # differential summary, per function
```

The `phonenumbers` version used for testing must match the libphonenumber metadata release
bundled in rlibphonenumber (`rphonenumbers.__phonenumbers_version__`).

## Linting

CI runs:

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
ruff check python tests benches
ruff format --check python tests benches
```

## Benchmarks

```bash
python benches/bench.py
```

See [Performance](performance.md) for published results and how they were measured.

## Releasing

See [RELEASING.md](../RELEASING.md).
