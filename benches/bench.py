"""Compare rphonenumbers against phonenumbers on common operations.

pip install phonenumbers
python benches/bench.py
"""

import timeit

import phonenumbers
import rphonenumbers

MATCHER_TEXT = (
    "Call our London office on +44 20 8366 1177 or the US line at (650) 253-0000. "
    "Support: 1-800-555-0199 (toll free), fax +1 650 253 0001. Invoice 2023-0042 dated "
    "12/03/2024, reference 98765432. Zürich +41 44 668 18 00, Berlin 030 1234567. "
) * 4


def corpus(lib):
    numbers = []
    for region in sorted(phonenumbers.SUPPORTED_REGIONS):
        for numtype in (0, 1):
            example = phonenumbers.example_number_for_type(region, numtype)
            if example is not None:
                numbers.append((phonenumbers.format_number(example, 2), region))
    return numbers


def cases(lib):
    gb = lib.parse("020 8366 1177", "GB")
    numbers = corpus(lib)

    def batch():
        for text, region in numbers:
            numobj = lib.parse(text, region)
            if lib.is_valid_number(numobj):
                lib.format_number(numobj, 0)

    return {
        "parse('+1 650-253-0000')": lambda: lib.parse("+1 650-253-0000", None),
        "parse('020 8366 1177', 'GB')": lambda: lib.parse("020 8366 1177", "GB"),
        "format_number(E164)": lambda: lib.format_number(gb, 0),
        "format_number(INTERNATIONAL)": lambda: lib.format_number(gb, 1),
        "is_valid_number": lambda: lib.is_valid_number(gb),
        "number_type": lambda: lib.number_type(gb),
        "parse + validate + E164, %d numbers" % len(numbers): batch,
        "PhoneNumberMatcher, %d chars" % len(MATCHER_TEXT): lambda: list(
            lib.PhoneNumberMatcher(MATCHER_TEXT, "US")
        ),
    }


def best_time(fn, repeat=5):
    number, _ = timeit.Timer(fn).autorange()
    return min(timeit.repeat(fn, number=number, repeat=repeat)) / number


def fmt(seconds):
    for unit, scale in (("s", 1), ("ms", 1e-3), ("µs", 1e-6), ("ns", 1e-9)):
        if seconds >= scale:
            return "%.2f %s" % (seconds / scale, unit)
    return "%.2f ns" % (seconds / 1e-9)


def main():
    upstream, ours = cases(phonenumbers), cases(rphonenumbers)
    print("phonenumbers %s vs rphonenumbers %s" % (phonenumbers.__version__, rphonenumbers.__version__))
    print("| Operation | phonenumbers | rphonenumbers | Speedup |")
    print("|---|---:|---:|---:|")
    for name in upstream:
        t_up, t_rs = best_time(upstream[name]), best_time(ours[name])
        print("| %s | %s | %s | %.1fx |" % (name, fmt(t_up), fmt(t_rs), t_up / t_rs))


if __name__ == "__main__":
    main()
