//! Native core of `rphonenumbers`, a drop-in replacement for the Python
//! `phonenumbers` package backed by the `rlibphonenumber` Rust crate.
//!
//! Every function here mirrors the name, signature and observable behaviour of
//! its counterpart in `phonenumbers.phonenumberutil`. The pure-Python wrapper
//! package re-exports them unchanged; it only owns the data classes
//! (`PhoneNumber`, `NumberFormat`, ...) and the integer "enum" classes.

use std::borrow::Cow;

use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyDict, PyList, PySet, PyString, PyTuple, PyType};
use pyo3::{IntoPyObjectExt, intern};

use rlibphonenumber::interfaces::AsOriginal;
use rlibphonenumber::phonenumber_matcher::{Leniency, PHONE_MATCHER_FACTORY};
use rlibphonenumber::{
    MatchType, NotANumberError, NumberFormat, NumberLengthType, PHONE_NUMBER_UTIL, ParseError,
    PhoneNumber, PhoneNumberFormat, PhoneNumberType, Region, ValidationError,
};

// Maximum input length accepted by `parse`, in characters (phonenumbers'
// `_MAX_INPUT_STRING_LENGTH`). The Rust crate does not enforce it.
const MAX_INPUT_STRING_LENGTH: usize = 250;

// NumberParseException.error_type values.
const INVALID_COUNTRY_CODE: i32 = 0;
const NOT_A_NUMBER: i32 = 1;
const TOO_SHORT_AFTER_IDD: i32 = 2;
const TOO_SHORT_NSN: i32 = 3;
const TOO_LONG: i32 = 4;

// MatchType.NOT_A_NUMBER
const MATCH_NOT_A_NUMBER: i32 = 0;

// Python classes owned by the pure-Python package, resolved lazily.
static PHONE_NUMBER_CLS: PyOnceLock<Py<PyType>> = PyOnceLock::new();
static FROZEN_PHONE_NUMBER_CLS: PyOnceLock<Py<PyType>> = PyOnceLock::new();
static PARSE_EXCEPTION_CLS: PyOnceLock<Py<PyType>> = PyOnceLock::new();
static OBJECT_NEW: PyOnceLock<Py<PyAny>> = PyOnceLock::new();

fn import_attr<'py>(
    py: Python<'py>,
    cell: &'static PyOnceLock<Py<PyType>>,
    module: &str,
    attr: &str,
) -> PyResult<&'py Bound<'py, PyType>> {
    cell.get_or_try_init(py, || {
        let obj = py.import(module)?.getattr(attr)?;
        Ok::<_, PyErr>(obj.cast_into::<PyType>()?.unbind())
    })
    .map(|cls| cls.bind(py))
}

fn phone_number_cls(py: Python<'_>) -> PyResult<&Bound<'_, PyType>> {
    import_attr(
        py,
        &PHONE_NUMBER_CLS,
        "rphonenumbers.phonenumber",
        "PhoneNumber",
    )
}

fn frozen_phone_number_cls(py: Python<'_>) -> PyResult<&Bound<'_, PyType>> {
    import_attr(
        py,
        &FROZEN_PHONE_NUMBER_CLS,
        "rphonenumbers.phonenumber",
        "FrozenPhoneNumber",
    )
}

fn parse_exception_cls(py: Python<'_>) -> PyResult<&Bound<'_, PyType>> {
    import_attr(
        py,
        &PARSE_EXCEPTION_CLS,
        "rphonenumbers.phonenumberutil",
        "NumberParseException",
    )
}

fn object_new(py: Python<'_>) -> PyResult<&Bound<'_, PyAny>> {
    OBJECT_NEW
        .get_or_try_init(py, || {
            Ok::<_, PyErr>(
                py.import("builtins")?
                    .getattr("object")?
                    .getattr("__new__")?
                    .unbind(),
            )
        })
        .map(|f| f.bind(py))
}

fn parse_exception(py: Python<'_>, error_type: i32, msg: &str) -> PyErr {
    match parse_exception_cls(py).and_then(|cls| cls.call1((error_type, msg))) {
        Ok(exc) => PyErr::from_value(exc),
        Err(err) => err,
    }
}

// ---------------------------------------------------------------------------
// PhoneNumber <-> Python object conversion
// ---------------------------------------------------------------------------

/// Attribute reader for PhoneNumber-like objects. Instances of our own
/// classes are read straight from their `__dict__`; anything else (user
/// subclasses, duck-typed objects such as an upstream `phonenumbers.PhoneNumber`)
/// goes through regular attribute access.
struct Fields<'a, 'py> {
    obj: &'a Bound<'py, PyAny>,
    dict: Option<Bound<'py, PyDict>>,
}

impl<'a, 'py> Fields<'a, 'py> {
    fn new(obj: &'a Bound<'py, PyAny>) -> PyResult<Self> {
        let py = obj.py();
        let ty = obj.get_type();
        let own = ty.is(phone_number_cls(py)?) || ty.is(frozen_phone_number_cls(py)?);
        let dict = if own {
            obj.getattr(intern!(py, "__dict__"))?
                .cast_into::<PyDict>()
                .ok()
        } else {
            None
        };
        Ok(Self { obj, dict })
    }

    fn get(&self, name: &Bound<'py, PyString>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(dict) = &self.dict
            && let Some(value) = dict.get_item(name)?
        {
            return Ok(value);
        }
        self.obj.getattr(name)
    }
}

/// Reads the eight PhoneNumber fields from any object exposing them.
fn extract_number(obj: &Bound<'_, PyAny>) -> PyResult<PhoneNumber> {
    let py = obj.py();
    let f = Fields::new(obj)?;
    let country_code: Option<i32> = f.get(intern!(py, "country_code"))?.extract()?;
    let national_number: Option<u64> = f.get(intern!(py, "national_number"))?.extract()?;
    let extension: Option<String> = f.get(intern!(py, "extension"))?.extract()?;
    let italian_leading_zero: Option<bool> = f
        .get(intern!(py, "italian_leading_zero"))?
        .extract::<Option<Bound<'_, PyAny>>>()?
        .map(|v| v.is_truthy())
        .transpose()?;
    let number_of_leading_zeros: Option<i32> =
        f.get(intern!(py, "number_of_leading_zeros"))?.extract()?;
    let raw_input: Option<String> = f.get(intern!(py, "raw_input"))?.extract()?;
    let country_code_source: Option<i32> = f.get(intern!(py, "country_code_source"))?.extract()?;
    let preferred_domestic_carrier_code: Option<String> = f
        .get(intern!(py, "preferred_domestic_carrier_code"))?
        .extract()?;

    Ok(PhoneNumber {
        country_code: country_code.unwrap_or(0),
        national_number: national_number.unwrap_or(0),
        extension,
        italian_leading_zero,
        number_of_leading_zeros,
        raw_input,
        country_code_source: country_code_source.filter(|&s| s != 0),
        preferred_domestic_carrier_code,
    })
}

/// Builds a fresh Python `PhoneNumber` without running its `__init__`: the
/// instance dict is populated directly, in the same key order `__init__` uses.
fn new_py_number<'py>(py: Python<'py>, n: &PhoneNumber) -> PyResult<Bound<'py, PyAny>> {
    let cls = phone_number_cls(py)?;
    let obj = object_new(py)?.call1((cls,))?;
    let dict = PyDict::new(py);
    dict.set_item(intern!(py, "country_code"), n.country_code)?;
    dict.set_item(intern!(py, "national_number"), n.national_number)?;
    dict.set_item(intern!(py, "extension"), n.extension.as_deref())?;
    dict.set_item(intern!(py, "italian_leading_zero"), n.italian_leading_zero)?;
    dict.set_item(
        intern!(py, "number_of_leading_zeros"),
        n.number_of_leading_zeros,
    )?;
    dict.set_item(intern!(py, "raw_input"), n.raw_input.as_deref())?;
    dict.set_item(
        intern!(py, "country_code_source"),
        n.country_code_source.unwrap_or(0),
    )?;
    dict.set_item(
        intern!(py, "preferred_domestic_carrier_code"),
        n.preferred_domestic_carrier_code.as_deref(),
    )?;
    obj.setattr(intern!(py, "__dict__"), dict)?;
    Ok(obj)
}

/// Writes a parse result into a caller-supplied `numobj`, touching only the
/// fields phonenumbers' `parse` assigns.
fn fill_py_number(obj: &Bound<'_, PyAny>, n: &PhoneNumber, keep_raw_input: bool) -> PyResult<()> {
    let py = obj.py();
    if keep_raw_input {
        obj.setattr(intern!(py, "raw_input"), n.raw_input.as_deref())?;
        obj.setattr(
            intern!(py, "country_code_source"),
            n.country_code_source.unwrap_or(0),
        )?;
    }
    if let Some(ext) = n.extension.as_deref() {
        obj.setattr(intern!(py, "extension"), ext)?;
    }
    obj.setattr(intern!(py, "country_code"), n.country_code)?;
    if let Some(cc) = n.preferred_domestic_carrier_code.as_deref() {
        obj.setattr(intern!(py, "preferred_domestic_carrier_code"), cc)?;
    }
    if let Some(ilz) = n.italian_leading_zero {
        obj.setattr(intern!(py, "italian_leading_zero"), ilz)?;
    }
    if let Some(nlz) = n.number_of_leading_zeros {
        obj.setattr(intern!(py, "number_of_leading_zeros"), nlz)?;
    }
    obj.setattr(intern!(py, "national_number"), n.national_number)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Enum conversions (phonenumbers uses plain ints)
// ---------------------------------------------------------------------------

fn format_from_int(value: i32) -> PyResult<PhoneNumberFormat> {
    match value {
        0 => Ok(PhoneNumberFormat::E164),
        1 => Ok(PhoneNumberFormat::International),
        2 => Ok(PhoneNumberFormat::National),
        3 => Ok(PhoneNumberFormat::RFC3966),
        _ => Err(PyValueError::new_err(format!(
            "Unknown PhoneNumberFormat value {value}"
        ))),
    }
}

fn type_to_int(t: PhoneNumberType) -> i32 {
    match t {
        PhoneNumberType::FixedLine => 0,
        PhoneNumberType::Mobile => 1,
        PhoneNumberType::FixedLineOrMobile => 2,
        PhoneNumberType::TollFree => 3,
        PhoneNumberType::PremiumRate => 4,
        PhoneNumberType::SharedCost => 5,
        PhoneNumberType::VoIP => 6,
        PhoneNumberType::PersonalNumber => 7,
        PhoneNumberType::Pager => 8,
        PhoneNumberType::UAN => 9,
        PhoneNumberType::VoiceMail => 10,
        PhoneNumberType::Unknown => 99,
    }
}

/// Unknown values fall back to `UNKNOWN`, which (like phonenumbers'
/// `_number_desc_by_type`) selects the general description.
fn type_from_int(value: i32) -> PhoneNumberType {
    match value {
        0 => PhoneNumberType::FixedLine,
        1 => PhoneNumberType::Mobile,
        2 => PhoneNumberType::FixedLineOrMobile,
        3 => PhoneNumberType::TollFree,
        4 => PhoneNumberType::PremiumRate,
        5 => PhoneNumberType::SharedCost,
        6 => PhoneNumberType::VoIP,
        7 => PhoneNumberType::PersonalNumber,
        8 => PhoneNumberType::Pager,
        9 => PhoneNumberType::UAN,
        10 => PhoneNumberType::VoiceMail,
        _ => PhoneNumberType::Unknown,
    }
}

fn validation_to_int(result: Result<NumberLengthType, ValidationError>) -> i32 {
    match result {
        Ok(NumberLengthType::IsPossible) => 0,
        Ok(NumberLengthType::IsPossibleLocalOnly) => 4,
        Err(ValidationError::InvalidCountryCode) => 1,
        Err(ValidationError::TooShort) => 2,
        Err(ValidationError::TooLong) => 3,
        Err(ValidationError::InvalidLength) => 5,
    }
}

fn match_type_to_int(m: MatchType) -> i32 {
    match m {
        MatchType::NoMatch => 1,
        MatchType::ShortNsnMatch => 2,
        MatchType::NsnMatch => 3,
        MatchType::ExactMatch => 4,
    }
}

fn leniency_from_int(value: i32) -> PyResult<Leniency> {
    match value {
        0 => Ok(Leniency::Possible),
        1 => Ok(Leniency::Valid),
        2 => Ok(Leniency::StrictGrouping),
        3 => Ok(Leniency::ExactGrouping),
        _ => Err(PyValueError::new_err(format!(
            "Unknown Leniency value {value}"
        ))),
    }
}

// ---------------------------------------------------------------------------
// Region codes
// ---------------------------------------------------------------------------

fn is_supported(region: Region) -> bool {
    PHONE_NUMBER_UTIL
        .get_country_code_for_region(region)
        .is_some()
}

/// phonenumbers' `_is_valid_region_code`: exact (case-sensitive) membership in
/// SUPPORTED_REGIONS, which excludes the non-geographic "001".
fn region_strict(code: Option<&str>) -> Option<Region> {
    let code = code?;
    if code.len() != 2 || !code.bytes().all(|b| b.is_ascii_uppercase()) {
        return None;
    }
    Region::from_code(code).ok().filter(|r| is_supported(*r))
}

/// `PhoneMetadata.metadata_for_region(region_code.upper())`: case-insensitive
/// lookup of a geographic region.
fn region_upper(code: &str) -> Option<Region> {
    if code.len() != 2 {
        return None;
    }
    Region::from_code(code).ok().filter(|r| is_supported(*r))
}

/// Calling-from regions: anything phonenumbers would reject as invalid maps to
/// a region without metadata, which every Rust formatter treats the same way.
fn calling_from(code: Option<&str>) -> Region {
    region_strict(code).unwrap_or(Region::ZZ)
}

fn region_str(region: Region) -> String {
    region.as_region_str().as_str().to_owned()
}

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

const MSG_NONE: &str = "The phone number supplied was None.";
const MSG_INPUT_TOO_LONG: &str = "The string supplied was too long to parse.";
const MSG_NOT_A_NUMBER: &str = "The string supplied did not seem to be a phone number.";
const MSG_BAD_PHONE_CONTEXT: &str = "The phone-context value is invalid";
const MSG_MISSING_REGION: &str = "Missing or invalid default region.";
const MSG_AFTER_PLUS: &str = "Could not interpret numbers after plus-sign.";
const MSG_BAD_COUNTRY_CODE: &str = "Country calling code supplied was not recognised.";
const MSG_TOO_SHORT_IDD: &str =
    "Phone number had an IDD, but after this was not long enough to be a viable phone number.";
const MSG_TOO_SHORT_NSN: &str = "The string supplied is too short to be a phone number.";
const MSG_TOO_LONG_NSN: &str = "The string supplied is too long to be a phone number.";

fn is_plus(c: char) -> bool {
    c == '+' || c == '\u{FF0B}'
}

/// Picks the message phonenumbers would attach to an INVALID_COUNTRY_CODE
/// error. The Rust crate reports a single variant for three distinct sites.
fn invalid_country_code_message(number: &str, region: Option<Region>) -> &'static str {
    let national = PHONE_NUMBER_UTIL
        .as_original()
        .build_national_number_for_parsing(number)
        .unwrap_or_default();
    let mut chars = national.chars();
    match chars.next() {
        Some(c) if is_plus(c) => {
            // After the plus is stripped the remainder is re-parsed; only a
            // second plus sign leads to the "not recognised" message.
            let rest = chars
                .as_str()
                .trim_start_matches(|c: char| !c.is_alphanumeric() && !is_plus(c));
            if rest.starts_with(is_plus) {
                MSG_BAD_COUNTRY_CODE
            } else {
                MSG_AFTER_PLUS
            }
        }
        _ if region.is_none() => MSG_MISSING_REGION,
        _ => MSG_BAD_COUNTRY_CODE,
    }
}

fn parse_error_to_py(
    py: Python<'_>,
    err: ParseError,
    number: &str,
    region: Option<Region>,
) -> PyErr {
    match err {
        ParseError::InvalidCountryCode => parse_exception(
            py,
            INVALID_COUNTRY_CODE,
            invalid_country_code_message(number, region),
        ),
        ParseError::NotANumber(NotANumberError::InvalidPhoneContext) => {
            parse_exception(py, NOT_A_NUMBER, MSG_BAD_PHONE_CONTEXT)
        }
        ParseError::NotANumber(_) => parse_exception(py, NOT_A_NUMBER, MSG_NOT_A_NUMBER),
        ParseError::TooShortAfterIdd => parse_exception(py, TOO_SHORT_AFTER_IDD, MSG_TOO_SHORT_IDD),
        ParseError::TooShortNsn => parse_exception(py, TOO_SHORT_NSN, MSG_TOO_SHORT_NSN),
        ParseError::TooLongNsn => parse_exception(py, TOO_LONG, MSG_TOO_LONG_NSN),
    }
}

/// Shared parse path: validates input the way phonenumbers does before
/// handing over to the Rust parser.
fn parse_rust(
    py: Python<'_>,
    number: &Bound<'_, PyAny>,
    region: Option<&str>,
    keep_raw_input: bool,
) -> PyResult<PhoneNumber> {
    if number.is_none() {
        return Err(parse_exception(py, NOT_A_NUMBER, MSG_NONE));
    }
    let number = number
        .cast::<PyString>()
        .map_err(|_| PyTypeError::new_err("number must be a str"))?
        .to_cow()?;
    if number.len() > MAX_INPUT_STRING_LENGTH && number.chars().count() > MAX_INPUT_STRING_LENGTH {
        return Err(parse_exception(py, TOO_LONG, MSG_INPUT_TOO_LONG));
    }
    let region = region_strict(region);
    let result = if keep_raw_input {
        PHONE_NUMBER_UTIL.parse_and_keep_raw_input(&*number, region)
    } else {
        PHONE_NUMBER_UTIL.parse(&*number, region)
    };
    result.map_err(|err| parse_error_to_py(py, err, &number, region))
}

/// parse(number, region=None, keep_raw_input=False, numobj=None, _check_region=True)
///
/// `_check_region` is accepted for signature compatibility only; region
/// checking is always performed.
#[pyfunction]
#[pyo3(signature = (number, region=None, keep_raw_input=false, numobj=None, _check_region=true))]
fn parse<'py>(
    py: Python<'py>,
    number: &Bound<'py, PyAny>,
    region: Option<&str>,
    keep_raw_input: bool,
    numobj: Option<&Bound<'py, PyAny>>,
    _check_region: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let parsed = parse_rust(py, number, region, keep_raw_input)?;
    match numobj {
        Some(obj) if !obj.is_none() => {
            fill_py_number(obj, &parsed, keep_raw_input)?;
            Ok(obj.clone())
        }
        _ => new_py_number(py, &parsed),
    }
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

#[pyfunction]
fn format_number(numobj: &Bound<'_, PyAny>, num_format: i32) -> PyResult<String> {
    let n = extract_number(numobj)?;
    Ok(PHONE_NUMBER_UTIL
        .format(&n, format_from_int(num_format)?)
        .into_owned())
}

/// Translates a Python `re.sub` replacement template (`\1`, `\g<1>`) into the
/// `regex` crate's syntax, escaping literal dollars.
///
/// `\N` becomes `$N` so libphonenumber's first-group detection (`\$\d`) sees
/// it exactly where phonenumbers' (`\\\d`) would; braces are only used when
/// the next character would otherwise extend the group name. `\g<N>` becomes
/// `${N}`, which, as in phonenumbers, is not treated as the first group.
fn python_template_to_rust(template: &str) -> String {
    let mut out = String::with_capacity(template.len() + 8);
    let mut chars = template.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '$' => out.push_str("$$"),
            '\\' => match chars.peek().copied() {
                Some(d) if d.is_ascii_digit() => {
                    chars.next();
                    let mut group = String::from(d);
                    if let Some(&d2) = chars.peek()
                        && d2.is_ascii_digit()
                    {
                        group.push(d2);
                        chars.next();
                    }
                    let extends_name = chars
                        .peek()
                        .is_some_and(|&next| next == '_' || next.is_ascii_alphanumeric());
                    if extends_name {
                        out.push_str("${");
                        out.push_str(&group);
                        out.push('}');
                    } else {
                        out.push('$');
                        out.push_str(&group);
                    }
                }
                Some('g') => {
                    chars.next();
                    if chars.peek() == Some(&'<') {
                        chars.next();
                        let name: String = chars.by_ref().take_while(|&ch| ch != '>').collect();
                        out.push_str("${");
                        out.push_str(&name);
                        out.push('}');
                    } else {
                        out.push_str("\\g");
                    }
                }
                Some('\\') => {
                    chars.next();
                    out.push('\\');
                }
                Some('n') => {
                    chars.next();
                    out.push('\n');
                }
                Some('t') => {
                    chars.next();
                    out.push('\t');
                }
                _ => out.push('\\'),
            },
            other => out.push(other),
        }
    }
    out
}

/// rlibphonenumber stores metadata patterns pre-anchored as `^(?:P)$` and
/// slices that string to obtain its anchored and unanchored variants, so user
/// patterns must take the same shape. Invalid patterns raise `re.error`, as
/// they do in phonenumbers, instead of panicking inside the crate.
fn wrap_pattern(py: Python<'_>, pattern: &str) -> PyResult<String> {
    let wrapped = format!("^(?:{pattern})$");
    match regex::Regex::new(&wrapped) {
        Ok(_) => Ok(wrapped),
        Err(err) => {
            let re_error = py.import("re")?.getattr("error")?;
            Err(PyErr::from_value(re_error.call1((err.to_string(),))?))
        }
    }
}

// `pattern` and `leading_digits_pattern` are marked deprecated because the
// crate's wrapper moves them out on conversion; setting them is the intended use.
#[allow(deprecated)]
fn extract_number_format(obj: &Bound<'_, PyAny>) -> PyResult<NumberFormat> {
    let py = obj.py();
    let pattern: Option<String> = obj.getattr(intern!(py, "pattern"))?.extract()?;
    let format: Option<String> = obj.getattr(intern!(py, "format"))?.extract()?;
    let leading_digits_pattern: Option<Vec<String>> = obj
        .getattr(intern!(py, "leading_digits_pattern"))?
        .extract()?;
    let national_prefix_formatting_rule: Option<String> = obj
        .getattr(intern!(py, "national_prefix_formatting_rule"))?
        .extract()?;
    let national_prefix_optional_when_formatting: Option<bool> = obj
        .getattr(intern!(py, "national_prefix_optional_when_formatting"))?
        .extract::<Option<Bound<'_, PyAny>>>()?
        .map(|v| v.is_truthy())
        .transpose()?;
    let domestic_carrier_code_formatting_rule: Option<String> = obj
        .getattr(intern!(py, "domestic_carrier_code_formatting_rule"))?
        .extract()?;
    let leading_digits_pattern = leading_digits_pattern
        .unwrap_or_default()
        .iter()
        .map(|p| wrap_pattern(py, p))
        .collect::<PyResult<Vec<_>>>()?;
    Ok(NumberFormat {
        pattern: wrap_pattern(py, &pattern.unwrap_or_default())?,
        format: python_template_to_rust(&format.unwrap_or_default()),
        leading_digits_pattern,
        national_prefix_formatting_rule,
        national_prefix_optional_when_formatting,
        domestic_carrier_code_formatting_rule,
    })
}

/// Calls `f` with the user formats converted to the crate's internal wrapper
/// type, which is public but not nameable from outside the crate.
fn with_wrapped_formats<W: From<NumberFormat>, R>(
    formats: Vec<NumberFormat>,
    f: impl FnOnce(&[W]) -> R,
) -> R {
    let wrapped: Vec<W> = formats.into_iter().map(W::from).collect();
    f(&wrapped)
}

#[pyfunction]
fn format_by_pattern(
    numobj: &Bound<'_, PyAny>,
    number_format: i32,
    user_defined_formats: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let mut n = extract_number(numobj)?;
    let number_format = format_from_int(number_format)?;
    let formats = user_defined_formats
        .try_iter()?
        .map(|item| extract_number_format(&item?))
        .collect::<PyResult<Vec<_>>>()?;
    // rlibphonenumber 2.2.14 always renders the extension in NATIONAL style
    // here; RFC3966 needs ";ext=", so append it ourselves.
    let rfc3966_extension = match number_format {
        PhoneNumberFormat::RFC3966 => n.extension.take().filter(|ext| !ext.is_empty()),
        _ => None,
    };
    let mut formatted = with_wrapped_formats(formats, |wrapped| {
        PHONE_NUMBER_UTIL.format_by_pattern(&n, number_format, wrapped)
    });
    if let Some(ext) = rfc3966_extension {
        formatted.push_str(";ext=");
        formatted.push_str(&ext);
    }
    Ok(formatted)
}

#[pyfunction]
fn format_in_original_format(
    numobj: &Bound<'_, PyAny>,
    region_calling_from: Option<&str>,
) -> PyResult<String> {
    let n = extract_number(numobj)?;
    Ok(PHONE_NUMBER_UTIL
        .format_in_original_format(&n, calling_from(region_calling_from))
        .into_owned())
}

#[pyfunction]
fn format_national_number_with_carrier_code(
    numobj: &Bound<'_, PyAny>,
    carrier_code: &str,
) -> PyResult<String> {
    let n = extract_number(numobj)?;
    Ok(PHONE_NUMBER_UTIL.format_national_number_with_carrier_code(&n, carrier_code))
}

#[pyfunction]
fn format_national_number_with_preferred_carrier_code(
    numobj: &Bound<'_, PyAny>,
    fallback_carrier_code: &str,
) -> PyResult<String> {
    let n = extract_number(numobj)?;
    Ok(PHONE_NUMBER_UTIL
        .format_national_number_with_preferred_carrier_code(&n, fallback_carrier_code))
}

#[pyfunction]
fn format_number_for_mobile_dialing(
    numobj: &Bound<'_, PyAny>,
    region_calling_from: Option<&str>,
    with_formatting: bool,
) -> PyResult<String> {
    let n = extract_number(numobj)?;
    // phonenumbers compares the calling region against the number's region
    // code verbatim, so "001" selects the non-geographical branch.
    let region = match region_calling_from {
        Some("001") => Region::World,
        other => calling_from(other),
    };
    Ok(PHONE_NUMBER_UTIL
        .format_number_for_mobile_dialing(&n, region, with_formatting)
        .map(Cow::into_owned)
        .unwrap_or_default())
}

#[pyfunction]
fn format_out_of_country_calling_number(
    numobj: &Bound<'_, PyAny>,
    region_calling_from: Option<&str>,
) -> PyResult<String> {
    let n = extract_number(numobj)?;
    Ok(PHONE_NUMBER_UTIL
        .format_out_of_country_calling_number(&n, calling_from(region_calling_from))
        .into_owned())
}

#[pyfunction]
fn format_out_of_country_keeping_alpha_chars(
    numobj: &Bound<'_, PyAny>,
    region_calling_from: Option<&str>,
) -> PyResult<String> {
    let n = extract_number(numobj)?;
    let strict = region_strict(region_calling_from);
    let formatted = PHONE_NUMBER_UTIL
        .format_out_of_country_keeping_alpha_chars(&n, strict.unwrap_or(Region::ZZ))
        .into_owned();
    // rlibphonenumber 2.2.14 treats a missing preferred international prefix
    // as an empty one and emits " <cc> ..." where libphonenumber falls back to
    // the international "+<cc> ..." form.
    let broken_head = format!(" {} ", n.country_code);
    if formatted.starts_with(&broken_head) {
        return Ok(format!("+{}", &formatted[1..]));
    }
    // phonenumbers looks the calling region's metadata up case-insensitively
    // here while its other checks are case-sensitive, so e.g. "us" dials out
    // with the US prefix ("011 44 ...") but never formats nationally.
    let intl_head = format!("+{} ", n.country_code);
    if strict.is_none()
        && !n.raw_input().is_empty()
        && formatted.starts_with(&intl_head)
        && let Some(prefix) = region_calling_from
            .and_then(region_upper)
            .and_then(international_prefix_for_formatting)
    {
        return Ok(format!(
            "{prefix} {} {}",
            n.country_code,
            &formatted[intl_head.len()..]
        ));
    }
    Ok(formatted)
}

/// libphonenumber's SINGLE_INTERNATIONAL_PREFIX: `\d+(?:[~⁓∼～]\d+)?`.
fn is_single_international_prefix(prefix: &str) -> bool {
    let all_digits = |s: &str| !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit());
    match prefix.split_once(['~', '\u{2053}', '\u{223C}', '\u{FF5E}']) {
        Some((head, tail)) => all_digits(head) && all_digits(tail),
        None => all_digits(prefix),
    }
}

/// The prefix used when dialling out of `region`, if it has an unambiguous one.
fn international_prefix_for_formatting(region: Region) -> Option<String> {
    let metadata = PHONE_NUMBER_UTIL
        .as_original()
        .get_metadata_for_region(region)?;
    let prefix = metadata.international_prefix().original_base();
    if is_single_international_prefix(prefix) {
        return Some(prefix.to_owned());
    }
    Some(
        metadata
            .original
            .preferred_international_prefix()
            .to_owned(),
    )
    .filter(|p| !p.is_empty())
}

// ---------------------------------------------------------------------------
// Validation and classification
// ---------------------------------------------------------------------------

#[pyfunction]
fn is_valid_number(numobj: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(PHONE_NUMBER_UTIL.is_valid_number(&extract_number(numobj)?))
}

#[pyfunction]
fn is_valid_number_for_region(
    numobj: &Bound<'_, PyAny>,
    region_code: Option<&str>,
) -> PyResult<bool> {
    let n = extract_number(numobj)?;
    let Some(code) = region_code else {
        return Ok(false);
    };
    let region = if code == "001" {
        Some(Region::World)
    } else {
        // rlibphonenumber 2.2.14 skips libphonenumber's check that the number's
        // country code belongs to the region, so it is done here.
        region_upper(code)
            .filter(|r| PHONE_NUMBER_UTIL.get_country_code_for_region(*r) == Some(n.country_code))
    };
    Ok(region.is_some_and(|r| PHONE_NUMBER_UTIL.is_valid_number_for_region(&n, r)))
}

#[pyfunction]
fn is_possible_number(numobj: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(PHONE_NUMBER_UTIL.is_possible_number(&extract_number(numobj)?))
}

#[pyfunction]
fn is_possible_number_for_type(numobj: &Bound<'_, PyAny>, numtype: i32) -> PyResult<bool> {
    let n = extract_number(numobj)?;
    Ok(PHONE_NUMBER_UTIL.is_possible_number_for_type(&n, type_from_int(numtype)))
}

#[pyfunction]
fn is_possible_number_with_reason(numobj: &Bound<'_, PyAny>) -> PyResult<i32> {
    let n = extract_number(numobj)?;
    Ok(validation_to_int(
        PHONE_NUMBER_UTIL.is_possible_number_with_reason(&n),
    ))
}

#[pyfunction]
fn is_possible_number_for_type_with_reason(
    numobj: &Bound<'_, PyAny>,
    numtype: i32,
) -> PyResult<i32> {
    let n = extract_number(numobj)?;
    Ok(validation_to_int(
        PHONE_NUMBER_UTIL.is_possible_number_for_type_with_reason(&n, type_from_int(numtype)),
    ))
}

#[pyfunction]
fn is_possible_number_string(
    py: Python<'_>,
    number: &Bound<'_, PyAny>,
    region_dialing_from: Option<&str>,
) -> PyResult<bool> {
    match parse_rust(py, number, region_dialing_from, false) {
        Ok(n) => Ok(PHONE_NUMBER_UTIL.is_possible_number(&n)),
        Err(err) if err.matches(py, parse_exception_cls(py)?)? => Ok(false),
        Err(err) => Err(err),
    }
}

#[pyfunction]
fn number_type(numobj: &Bound<'_, PyAny>) -> PyResult<i32> {
    Ok(type_to_int(
        PHONE_NUMBER_UTIL.get_number_type(&extract_number(numobj)?),
    ))
}

#[pyfunction]
fn region_code_for_number(numobj: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
    let n = extract_number(numobj)?;
    Ok(PHONE_NUMBER_UTIL.get_region_for_number(&n).map(region_str))
}

#[pyfunction]
fn can_be_internationally_dialled(numobj: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(PHONE_NUMBER_UTIL.can_be_internationally_dialled(&extract_number(numobj)?))
}

#[pyfunction]
fn is_number_geographical(numobj: &Bound<'_, PyAny>) -> PyResult<bool> {
    Ok(PHONE_NUMBER_UTIL.is_number_geographical(&extract_number(numobj)?))
}

#[pyfunction]
fn is_number_type_geographical(num_type: i32, country_code: i32) -> bool {
    PHONE_NUMBER_UTIL
        .is_number_geographical_by_country_code_and_type(type_from_int(num_type), country_code)
}

#[pyfunction]
fn length_of_geographical_area_code(numobj: &Bound<'_, PyAny>) -> PyResult<usize> {
    Ok(PHONE_NUMBER_UTIL.get_length_of_geographical_area_code(&extract_number(numobj)?))
}

#[pyfunction]
fn length_of_national_destination_code(numobj: &Bound<'_, PyAny>) -> PyResult<usize> {
    Ok(PHONE_NUMBER_UTIL.get_length_of_national_destination_code(&extract_number(numobj)?))
}

#[pyfunction]
fn truncate_too_long_number(numobj: &Bound<'_, PyAny>) -> PyResult<bool> {
    let mut n = extract_number(numobj)?;
    let original = n.national_number;
    let truncated = PHONE_NUMBER_UTIL.truncate_too_long_number(&mut n);
    if truncated && n.national_number != original {
        numobj.setattr(intern!(numobj.py(), "national_number"), n.national_number)?;
    }
    Ok(truncated)
}

// ---------------------------------------------------------------------------
// Number matching
// ---------------------------------------------------------------------------

#[pyfunction]
fn is_number_match(num1: &Bound<'_, PyAny>, num2: &Bound<'_, PyAny>) -> PyResult<i32> {
    let as_str = |obj: &Bound<'_, PyAny>| -> PyResult<Option<String>> {
        match obj.cast::<PyString>() {
            Ok(s) => Ok(Some(s.to_cow()?.into_owned())),
            Err(_) => Ok(None),
        }
    };
    let result = match (as_str(num1)?, as_str(num2)?) {
        (None, None) => {
            Ok(PHONE_NUMBER_UTIL.is_number_match(&extract_number(num1)?, &extract_number(num2)?))
        }
        (None, Some(s2)) => {
            PHONE_NUMBER_UTIL.is_number_match_with_one_string(&extract_number(num1)?, &s2)
        }
        (Some(s1), None) => {
            PHONE_NUMBER_UTIL.is_number_match_with_one_string(&extract_number(num2)?, &s1)
        }
        (Some(s1), Some(s2)) => PHONE_NUMBER_UTIL.is_number_match_with_two_strings(&s1, &s2),
    };
    Ok(result.map(match_type_to_int).unwrap_or(MATCH_NOT_A_NUMBER))
}

// ---------------------------------------------------------------------------
// String normalization
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (number, keep_non_digits=false))]
fn normalize_digits_only(number: &Bound<'_, PyAny>, keep_non_digits: bool) -> PyResult<String> {
    let number = number.str()?;
    let number = number.to_cow()?;
    if !keep_non_digits {
        return Ok(PHONE_NUMBER_UTIL.normalize_digits_only(&*number));
    }
    let mut out = String::with_capacity(number.len());
    let mut buf = [0u8; 4];
    for c in number.chars() {
        if c.is_ascii_digit() {
            out.push(c);
            continue;
        }
        let digit = PHONE_NUMBER_UTIL.normalize_digits_only(&*c.encode_utf8(&mut buf));
        if digit.is_empty() {
            out.push(c);
        } else {
            out.push_str(&digit);
        }
    }
    Ok(out)
}

#[pyfunction]
fn normalize_diallable_chars_only(number: &str) -> String {
    PHONE_NUMBER_UTIL.normalize_diallable_chars_only(number)
}

#[pyfunction]
fn convert_alpha_characters_in_number(number: &str) -> String {
    PHONE_NUMBER_UTIL.convert_alpha_characters_in_number(number)
}

#[pyfunction]
fn is_alpha_number(number: &str) -> bool {
    PHONE_NUMBER_UTIL.is_alpha_number(number)
}

// ---------------------------------------------------------------------------
// Metadata queries
// ---------------------------------------------------------------------------

#[pyfunction]
fn country_mobile_token(country_code: i32) -> String {
    PHONE_NUMBER_UTIL
        .get_country_mobile_token(country_code)
        .map(String::from)
        .unwrap_or_default()
}

#[pyfunction]
fn is_mobile_number_portable_region(region_code: Option<&str>) -> bool {
    region_strict(region_code)
        .and_then(|r| PHONE_NUMBER_UTIL.as_original().get_metadata_for_region(r))
        .is_some_and(|m| m.original.mobile_number_portable_region())
}

#[pyfunction]
fn ndd_prefix_for_region(region_code: Option<&str>, strip_non_digits: bool) -> Option<String> {
    let region = region_upper(region_code?)?;
    PHONE_NUMBER_UTIL
        .as_original()
        .get_ndd_prefix_for_region(region, strip_non_digits)
        .filter(|p| !p.is_empty())
}

fn type_set<'py>(
    py: Python<'py>,
    types: Option<impl IntoIterator<Item = PhoneNumberType>>,
) -> PyResult<Bound<'py, PySet>> {
    let set = PySet::empty(py)?;
    for t in types.into_iter().flatten() {
        if !matches!(
            t,
            PhoneNumberType::FixedLineOrMobile | PhoneNumberType::Unknown
        ) {
            set.add(type_to_int(t))?;
        }
    }
    Ok(set)
}

#[pyfunction]
fn supported_types_for_region<'py>(
    py: Python<'py>,
    region_code: Option<&str>,
) -> PyResult<Bound<'py, PySet>> {
    let types = region_strict(region_code)
        .and_then(|r| PHONE_NUMBER_UTIL.get_supported_types_for_region(r));
    type_set(py, types)
}

#[pyfunction]
fn supported_types_for_non_geo_entity(
    py: Python<'_>,
    country_code: i32,
) -> PyResult<Bound<'_, PySet>> {
    type_set(
        py,
        PHONE_NUMBER_UTIL.get_supported_types_for_non_geo_entity(country_code),
    )
}

#[pyfunction]
fn example_number<'py>(
    py: Python<'py>,
    region_code: Option<&str>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    example_number_for_type(py, region_code, 0)
}

#[pyfunction]
fn example_number_for_type<'py>(
    py: Python<'py>,
    region_code: Option<&str>,
    num_type: i32,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let num_type = type_from_int(num_type);
    let result = match region_code {
        None => PHONE_NUMBER_UTIL.get_example_number_for_type(num_type),
        Some(code) => match region_strict(Some(code)) {
            Some(region) => {
                PHONE_NUMBER_UTIL.get_example_number_for_type_and_region(region, num_type)
            }
            None => return Ok(None),
        },
    };
    result.ok().map(|n| new_py_number(py, &n)).transpose()
}

#[pyfunction]
fn invalid_example_number<'py>(
    py: Python<'py>,
    region_code: Option<&str>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let Some(region) = region_strict(region_code) else {
        return Ok(None);
    };
    PHONE_NUMBER_UTIL
        .get_invalid_example_number(region)
        .ok()
        .map(|n| new_py_number(py, &n))
        .transpose()
}

#[pyfunction]
fn example_number_for_non_geo_entity(
    py: Python<'_>,
    country_calling_code: i32,
) -> PyResult<Option<Bound<'_, PyAny>>> {
    PHONE_NUMBER_UTIL
        .get_example_number_for_non_geo_entity(country_calling_code)
        .ok()
        .map(|n| new_py_number(py, &n))
        .transpose()
}

// ---------------------------------------------------------------------------
// Static tables, built once by the Python package at import time
// ---------------------------------------------------------------------------

/// {country_code: (main_region, other_regions...)}, as in
/// phonenumbers' COUNTRY_CODE_TO_REGION_CODE.
#[pyfunction]
fn _country_code_to_region_code(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new(py);
    let mut codes: Vec<i32> = PHONE_NUMBER_UTIL.get_supported_calling_codes().collect();
    codes.sort_unstable();
    codes.dedup();
    for code in codes {
        let regions: Vec<String> = PHONE_NUMBER_UTIL
            .get_regions_for_country_calling_code(code)
            .map(|it| it.map(region_str).collect())
            .unwrap_or_default();
        dict.set_item(code, PyTuple::new(py, regions)?)?;
    }
    Ok(dict)
}

/// {region_code: country_code} for every geographic region.
#[pyfunction]
fn _region_to_country_code(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let dict = PyDict::new(py);
    for region in PHONE_NUMBER_UTIL.get_supported_regions() {
        if let Some(code) = PHONE_NUMBER_UTIL.get_country_code_for_region(region) {
            dict.set_item(region_str(region), code)?;
        }
    }
    Ok(dict)
}

#[pyfunction]
fn _non_geo_country_codes(py: Python<'_>) -> PyResult<Bound<'_, PySet>> {
    PySet::new(
        py,
        PHONE_NUMBER_UTIL.get_supported_global_network_calling_codes(),
    )
}

// ---------------------------------------------------------------------------
// PhoneNumberMatcher support
// ---------------------------------------------------------------------------

/// Finds all phone numbers in `text`, returning (start, raw_string, numobj)
/// tuples with `start` as a character (not byte) offset.
#[pyfunction]
fn _find_numbers<'py>(
    py: Python<'py>,
    text: &str,
    region: Option<&str>,
    leniency: i32,
    max_tries: u64,
) -> PyResult<Bound<'py, PyList>> {
    let matcher = PHONE_MATCHER_FACTORY
        .matcher_builder(text)
        .preferred_region(region_strict(region))
        .leniency(leniency_from_int(leniency)?)
        .max_tries(max_tries)
        .build();
    let out = PyList::empty(py);
    let (mut byte_pos, mut char_pos) = (0usize, 0usize);
    for m in matcher {
        char_pos += text[byte_pos..m.start].chars().count();
        byte_pos = m.start;
        let numobj = new_py_number(py, &m.number)?;
        let item = (char_pos, m.raw_string, numobj).into_bound_py_any(py)?;
        out.append(item)?;
    }
    Ok(out)
}

#[pymodule(gil_used = false)]
fn _rphonenumbers(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Cargo.toml is the single source of the package version.
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    m.add_function(wrap_pyfunction!(format_number, m)?)?;
    m.add_function(wrap_pyfunction!(format_by_pattern, m)?)?;
    m.add_function(wrap_pyfunction!(format_in_original_format, m)?)?;
    m.add_function(wrap_pyfunction!(
        format_national_number_with_carrier_code,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        format_national_number_with_preferred_carrier_code,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(format_number_for_mobile_dialing, m)?)?;
    m.add_function(wrap_pyfunction!(format_out_of_country_calling_number, m)?)?;
    m.add_function(wrap_pyfunction!(
        format_out_of_country_keeping_alpha_chars,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(is_valid_number, m)?)?;
    m.add_function(wrap_pyfunction!(is_valid_number_for_region, m)?)?;
    m.add_function(wrap_pyfunction!(is_possible_number, m)?)?;
    m.add_function(wrap_pyfunction!(is_possible_number_for_type, m)?)?;
    m.add_function(wrap_pyfunction!(is_possible_number_with_reason, m)?)?;
    m.add_function(wrap_pyfunction!(
        is_possible_number_for_type_with_reason,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(is_possible_number_string, m)?)?;
    m.add_function(wrap_pyfunction!(number_type, m)?)?;
    m.add_function(wrap_pyfunction!(region_code_for_number, m)?)?;
    m.add_function(wrap_pyfunction!(can_be_internationally_dialled, m)?)?;
    m.add_function(wrap_pyfunction!(is_number_geographical, m)?)?;
    m.add_function(wrap_pyfunction!(is_number_type_geographical, m)?)?;
    m.add_function(wrap_pyfunction!(length_of_geographical_area_code, m)?)?;
    m.add_function(wrap_pyfunction!(length_of_national_destination_code, m)?)?;
    m.add_function(wrap_pyfunction!(truncate_too_long_number, m)?)?;
    m.add_function(wrap_pyfunction!(is_number_match, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_digits_only, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_diallable_chars_only, m)?)?;
    m.add_function(wrap_pyfunction!(convert_alpha_characters_in_number, m)?)?;
    m.add_function(wrap_pyfunction!(is_alpha_number, m)?)?;
    m.add_function(wrap_pyfunction!(country_mobile_token, m)?)?;
    m.add_function(wrap_pyfunction!(is_mobile_number_portable_region, m)?)?;
    m.add_function(wrap_pyfunction!(ndd_prefix_for_region, m)?)?;
    m.add_function(wrap_pyfunction!(supported_types_for_region, m)?)?;
    m.add_function(wrap_pyfunction!(supported_types_for_non_geo_entity, m)?)?;
    m.add_function(wrap_pyfunction!(example_number, m)?)?;
    m.add_function(wrap_pyfunction!(example_number_for_type, m)?)?;
    m.add_function(wrap_pyfunction!(invalid_example_number, m)?)?;
    m.add_function(wrap_pyfunction!(example_number_for_non_geo_entity, m)?)?;
    m.add_function(wrap_pyfunction!(_country_code_to_region_code, m)?)?;
    m.add_function(wrap_pyfunction!(_region_to_country_code, m)?)?;
    m.add_function(wrap_pyfunction!(_non_geo_country_codes, m)?)?;
    m.add_function(wrap_pyfunction!(_find_numbers, m)?)?;
    Ok(())
}
