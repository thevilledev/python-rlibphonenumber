# Performance

[`benches/bench.py`](../benches/bench.py) times common operations in `phonenumbers` and
rphonenumbers side by side. Each case runs under `timeit` and keeps the best of 5 repeats; the
tables below show the median of 3 runs.

Both machines ran the same build of CPython 3.14.8 (python-build-standalone 20261009), the
rphonenumbers 0.1.0 wheels from PyPI and `phonenumbers` 9.0.41.

## Apple M1 Max

macOS 27.0.1, arm64.

| Operation | phonenumbers | rphonenumbers | Speedup |
|---|---:|---:|---:|
| `parse("+1 650-253-0000")` | 8.10 µs | 788 ns | 10.3x |
| `parse("020 8366 1177", "GB")` | 10.31 µs | 789 ns | 13.1x |
| `format_number(E164)` | 246 ns | 227 ns | 1.1x |
| `format_number(INTERNATIONAL)` | 3.61 µs | 651 ns | 5.5x |
| `is_valid_number` | 7.99 µs | 486 ns | 16.4x |
| `number_type` | 7.75 µs | 488 ns | 15.9x |
| parse + validate + E164, 489 numbers across all regions | 65.61 ms | 1.04 ms | 63.1x |
| `PhoneNumberMatcher`, 944 chars | 877 µs | 78 µs | 11.2x |

## AMD Ryzen AI 9 HX PRO 370

Linux 6.18 (Manjaro), x86_64, pinned with `taskset -c 2` to one of the full Zen 5 cores rather
than the slower Zen 5c cores.

| Operation | phonenumbers | rphonenumbers | Speedup |
|---|---:|---:|---:|
| `parse("+1 650-253-0000")` | 5.71 µs | 632 ns | 9.0x |
| `parse("020 8366 1177", "GB")` | 7.22 µs | 630 ns | 11.5x |
| `format_number(E164)` | 169 ns | 148 ns | 1.1x |
| `format_number(INTERNATIONAL)` | 2.73 µs | 535 ns | 5.1x |
| `is_valid_number` | 5.94 µs | 408 ns | 14.6x |
| `number_type` | 5.68 µs | 410 ns | 13.9x |
| parse + validate + E164, 489 numbers across all regions | 54.56 ms | 725 µs | 75.2x |
| `PhoneNumberMatcher`, 944 chars | 732 µs | 56 µs | 13.1x |

## Notes

- E164 formatting is already a string concatenation in `phonenumbers`, so there is nothing to win
  there.
- The mixed-region batch gains the most because `phonenumbers` recompiles regexes once Python's
  `re` cache (512 entries) overflows.
- The Ryzen is 1.2–1.5x faster than the M1 Max on every operation. For parsing, validation and
  INTERNATIONAL formatting, pure-Python `phonenumbers` gains more from the faster CPU than
  rphonenumbers does, so those speedups are slightly lower on the Ryzen. The batch and matcher
  cases go the other way.

## Reproducing

```bash
pip install rphonenumbers phonenumbers==9.0.41
python benches/bench.py
```

On CPUs with both performance and efficiency cores, pin the benchmark to a performance core (for
example `taskset -c <cpu> python benches/bench.py` on Linux) so the two libraries are measured on
the same kind of core.
