"""Deterministic input corpus for differential tests against ``phonenumbers``.

Inputs are derived from the upstream library's own example numbers, so the
corpus tracks the metadata version both libraries are built from.
"""

import random

import phonenumbers as upstream

ALL_TYPES = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 99)
FORMATS = (0, 1, 2, 3)

# Region arguments exercising phonenumbers' case-sensitive region checks.
EDGE_REGIONS = (None, "ZZ", "001", "us", "Gb", "XX", "", "USA")

CALLING_FROM = (
    "US",
    "GB",
    "DE",
    "FR",
    "JP",
    "BR",
    "AU",
    "IT",
    "CH",
    "SG",
    "MX",
    "CL",
    "UZ",
    "KR",
    "IN",
) + EDGE_REGIONS

HANDWRITTEN = [
    "+1 650 253 0000",
    "1-800-FLOWERS",
    "1-800-SIX-FLAG",
    "0800 FLOWERS",
    "+44 (0) 20 8366 1177",
    "+44 20 8366 1177 ext. 123",
    "+1 650-253-0000 x1234",
    "650-253-0000 extension 9",
    "tel:+1-650-253-0000;phone-context=+1",
    "tel:253-0000;phone-context=+1-650",
    "tel:253-0000;phone-context=www.google.com",
    "tel:253-0000;phone-context=;a",
    "tel:+1-650-253-0000;isub=12345",
    "tel:2530000;phone-context=+64-3",
    "+１６５０２５３００００",  # full-width digits
    "١٢٣٤٥٦٧٨",  # Arabic-Indic digits
    "+49 30 1234567",
    "030 1234567",
    "0049 30 1234567",
    "011 44 20 8366 1177",
    "00 1 650 253 0000",
    "+800 1234 5678",
    "+979 123 456 789",
    "+39 02 3661 8300",
    "02 3661 8300",
    "+39 0000 000",
    "+390236618300",
    "+61 1800 123 456",
    "+55 11 98765 4321",
    "0xx11 98765 4321",
    "0 15 11 98765 4321",
    "+52 1 55 1234 5678",
    "+7 495 123 45 67",
    "8 495 123 45 67",
    "+86 10 1234 5678",
    "+81 3-1234-5678",
    "+999 1234567",
    "+1",
    "+",
    "++44 20 8366 1177",
    "+0 123456",
    "123",
    "12",
    "1",
    "",
    "   ",
    "abc",
    "foo +1 650 253 0000 bar",
    "+1 (650) 253-0000;ext=99",
    "+1 650 253 0000#",
    "*123#",
    "+44 7912 345 678",
    "07912 345678",
    "+353 1 234 5678",
    "+376 123456",
    "+1 242 357 1234",
    "+1 800 555 0199",
    "+1 900 555 0199",
    "+64 3 331 6005",
    "+262 262 12 34 56",
    "+290 8 1234",
    "+1 21 2 2",
    "0" * 20,
    "1" * 30,
    "+1" + "2" * 20,
    "9" * 251,
    "+49 1234 56789012345678",
    "+1 650 253 0000 ext. 12345678901234567890",
    "(650) 253-0000",
    "650 253 0000",
    "6502530000",
    "16502530000",
    "+16502530000",
]


def _variants(rng, example, region, cc):
    """Yield textual variants of a national example number."""
    yield example
    yield "+%d%s" % (cc, example)
    yield "+%d %s" % (cc, example)
    yield "00%d%s" % (cc, example)
    yield "011%d%s" % (cc, example)
    yield "%d%s" % (cc, example)
    yield example[:-1]
    yield example + "9"
    yield example + " ext. 42"
    yield "0" + example
    if len(example) > 4:
        mid = len(example) // 2
        yield "(%s) %s-%s" % (example[:3], example[3:mid], example[mid:])
        yield example[:2] + "." + example[2:]
    digits = list(example)
    rng.shuffle(digits)
    yield "".join(digits)


def number_strings(seed=1234):
    """(number_string, region) pairs for parse-level comparisons."""
    rng = random.Random(seed)
    pairs = []
    for region in sorted(upstream.SUPPORTED_REGIONS):
        metadata = upstream.PhoneMetadata.metadata_for_region(region)
        cc = metadata.country_code
        examples = set()
        for numtype in ALL_TYPES:
            desc = upstream.phonenumberutil._number_desc_by_type(metadata, numtype)
            if desc is not None and desc.example_number:
                examples.add(desc.example_number)
        for example in sorted(examples):
            for variant in _variants(rng, example, region, cc):
                pairs.append((variant, region))
            # The same strings without a default region, and from a neighbour.
            pairs.append(("+%d%s" % (cc, example), None))
            pairs.append((example, rng.choice(("US", "GB", "DE", "ZZ", None, region.lower()))))
    for cc in sorted(upstream.COUNTRY_CODES_FOR_NON_GEO_REGIONS):
        metadata = upstream.PhoneMetadata.metadata_for_nongeo_region(cc)
        for numtype in ALL_TYPES:
            desc = upstream.phonenumberutil._number_desc_by_type(metadata, numtype)
            if desc is not None and desc.example_number:
                pairs.append(("+%d %s" % (cc, desc.example_number), None))
                pairs.append(("+%d%s9" % (cc, desc.example_number), "US"))
    for text in HANDWRITTEN:
        for region in ("US", "GB", "DE", "IT", "BR", "NZ") + EDGE_REGIONS:
            pairs.append((text, region))
    return pairs


MATCHER_TEXTS = [
    "Call me at 510-748-8230 if it's before 9:30, or on 703-4800500 after 10am.",
    "Office: +44 20 8366 1177, mobile 07912 345678 (UK).",
    "Numbers: +1 650 253 0000 / +41 44 668 1800 / 1-800-FLOWERS",
    "Price 2009-2010 $1,234.56 on 1/2/2012 ticket 12345678",
    "Berlin 030 1234567 or München +49 89 1234567",
    "Zürich: +41 44 668 18 00 — Ελλάδα +30 21 0123 4567 — 東京 +81 3-1234-5678",
    "tel:+1-650-253-0000 and (650) 253-0000 x123",
    "+33 1 23 45 67 89, 01 23 45 67 89, 0033 1 23 45 67 89",
    "",
    "no numbers here at all",
]
