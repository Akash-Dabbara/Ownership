import polars as pl
import string
import hashlib
import re
import datetime

DEFAULT_SEED = 2026

# ==============================================================================
# 1. CHARACTER & STRINGS POOLS DEFINITIONS
# ==============================================================================
UPPER_ALPHABET = list(string.ascii_uppercase)
LOWER_ALPHABET = list(string.ascii_lowercase)
DIGITS_POOL = list(string.digits)

DOMAINS_POOL = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "mail.com", "icloud.com", "protonmail.com"]

CONSONANTS = ["b", "c", "d", "f", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "y", "z", "ch", "sh"]
VOWELS = ["a", "e", "i", "o", "u", "an", "al", "ar", "ia"]
C_KEYS = list(range(len(CONSONANTS)))
V_KEYS = list(range(len(VOWELS)))

SUPPORTED_DATE_FORMATS = {
    "DD-MM-YYYY (Numeric)": {"pattern": "%d-%m-%Y"},
    "MM-DD-YYYY (Numeric)": {"pattern": "%m-%d-%Y"},
    "YYYY-MM-DD (Numeric)": {"pattern": "%Y-%m-%d"},
    "DD/MM/YYYY (Numeric)": {"pattern": "%d/%m/%Y"},
    "MM/DD/YYYY (Numeric)": {"pattern": "%m/%d/%Y"},
    "YYYY/MM/DD (Numeric)": {"pattern": "%Y/%m/%d"},
    "DD-MMM-YYYY (Alpha Month)": {"pattern": "%d-%b-%Y"},
    "MMM-DD-YYYY (Alpha Month)": {"pattern": "%b-%d-%Y"},
    "DD/MMM/YYYY (Alpha Month)": {"pattern": "%d/%b/%Y"},
    "DD-MMM-YY (Alpha Month)": {"pattern": "%d-%b-%y"},
    "DD.MM.YYYY (Dot Separator)": {"pattern": "%d.%m.%Y"},
    "MM.DD.YYYY (Dot Separator)": {"pattern": "%m.%d.%Y"},
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+]?[\d\-\s()]{7,15}$")
_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")

# ==============================================================================
# 2. INNER HELPER ENTROPY & MASKING METHODS
# ==============================================================================
def calculate_md5_hash_string(val: str) -> str:
    if val is None:
        val = "NULL"
    return hashlib.md5(val.encode("utf-8")).hexdigest()

def _get_string_entropy_expr(expr: pl.Expr, salt: str, seed: int) -> pl.Expr:
    cleaned = expr.cast(pl.String).str.strip_chars().fill_null("NULL")
    return (cleaned + pl.lit(salt) + pl.lit(str(seed))).hash(seed=seed)

def _get_string_hash(str_expr: pl.Expr, seed: int = DEFAULT_SEED) -> pl.Expr:
    return str_expr.cast(pl.String).fill_null("NULL").hash(seed=seed)

def _generate_first_name_from_expr(expr: pl.Expr, seed: int = DEFAULT_SEED) -> pl.Expr:
    h = _get_string_hash(expr, seed=seed)
    return (
        (h % len(CONSONANTS)).cast(pl.Int64).replace_strict(C_KEYS, CONSONANTS, default=None) +
        ((h + 1) % len(VOWELS)).cast(pl.Int64).replace_strict(V_KEYS, VOWELS, default=None) +
        ((h + 2) % len(CONSONANTS)).cast(pl.Int64).replace_strict(C_KEYS, CONSONANTS, default=None) +
        ((h + 3) % len(VOWELS)).cast(pl.Int64).replace_strict(V_KEYS, VOWELS, default=None)
    ).str.to_titlecase()

def _generate_last_name_from_expr(expr: pl.Expr, seed: int = DEFAULT_SEED) -> pl.Expr:
    h = _get_string_hash(expr, seed=seed)
    return (
        ((h + 5) % len(CONSONANTS)).cast(pl.Int64).replace_strict(C_KEYS, CONSONANTS, default=None) +
        ((h + 6) % len(VOWELS)).cast(pl.Int64).replace_strict(V_KEYS, VOWELS, default=None) +
        ((h + 7) % len(CONSONANTS)).cast(pl.Int64).replace_strict(C_KEYS, CONSONANTS, default=None) +
        pl.lit("ur")
    ).str.to_titlecase()

def _generate_exact_full_name_from_expr(expr: pl.Expr, seed: int = DEFAULT_SEED) -> pl.Expr:
    tokens = expr.cast(pl.String).str.replace_all(r"\s+", " ").str.strip_chars().str.split(" ")
    return tokens.list.eval(
        pl.when(pl.element().cum_count() == pl.element().count())
        .then(_generate_last_name_from_expr(pl.element(), seed))
        .otherwise(_generate_first_name_from_expr(pl.element(), seed))
    ).list.join(" ")

def rebuild_with_format(original_value: str, replacement_digits: str) -> str:
    if original_value is None or original_value == "":
        return None
    rebuilt = []
    digit_idx = 0
    for ch in original_value:
        if ch.isdigit():
            if digit_idx < len(replacement_digits):
                rebuilt.append(replacement_digits[digit_idx])
                digit_idx += 1
            else:
                rebuilt.append(ch)
        else:
            rebuilt.append(ch)
    return "".join(rebuilt)

# ==============================================================================
# 3. HIGH-VELOCITY VECTORIZED EMAIL GENERATION INNER MODULE
# ==============================================================================
def _vectorized_email_masker(
    col_expr: pl.Expr,
    seed: int,
    match_names: bool = False,
    rules_dict: dict = None,
    active_table: str = "",
    df_cols: list = None
) -> pl.Expr:
    entropy = _get_string_entropy_expr(col_expr, "FabricEmailMasking2026_v1", seed)
    domain_idx = (entropy % len(DOMAINS_POOL)).cast(pl.Int64)
    domain_str = domain_idx.replace_strict(list(range(len(DOMAINS_POOL))), DOMAINS_POOL, default=DOMAINS_POOL[0])

    if match_names and rules_dict and active_table and df_cols:
        fn_col, ln_col, full_col = None, None, None
        for c in df_cols:
            rk = f"{active_table}|{c}"
            algo = rules_dict.get(rk, {}).get("algo", "")
            if algo in ["First Name", "FIRSTNAME"] and not fn_col:
                fn_col = c
            elif algo in ["Last Name", "LASTNAME"] and not ln_col:
                ln_col = c
            elif algo in ["Full Name", "FULLNAME"] and not full_col:
                full_col = c

        first_expr, last_expr = None, None
        if fn_col:
            first_expr = _generate_first_name_from_expr(pl.col(fn_col), seed).str.to_lowercase()
        if ln_col:
            last_expr = _generate_last_name_from_expr(pl.col(ln_col), seed).str.to_lowercase()
        elif full_col:
            tokens = pl.col(full_col).cast(pl.String).str.replace_all(r"\s+", " ").str.strip_chars().str.split(" ")
            first_expr = _generate_first_name_from_expr(tokens.list.get(0), seed).str.to_lowercase()
            last_expr = _generate_last_name_from_expr(tokens.list.get(-1), seed).str.to_lowercase()

        if first_expr is not None and last_expr is not None:
            return first_expr + pl.lit(".") + last_expr + pl.lit("@") + domain_str
        elif first_expr is not None:
            return first_expr + pl.lit("@") + domain_str

    u_h = entropy.hash(seed=seed)
    u_part1 = (u_h % len(CONSONANTS)).cast(pl.Int64).replace_strict(C_KEYS, CONSONANTS, default=None)
    u_part2 = ((u_h + 1) % len(VOWELS)).cast(pl.Int64).replace_strict(V_KEYS, VOWELS, default=None)
    u_part3 = ((u_h + 2) % len(CONSONANTS)).cast(pl.Int64).replace_strict(C_KEYS, CONSONANTS, default=None)
    u_num = ((u_h % 899) + 100).cast(pl.String)
    username = u_part1 + u_part2 + u_part3 + u_num

    return username + pl.lit("@") + domain_str

# ==============================================================================
# 4. PHONE NUMBER MASKING
# ==============================================================================
def _mask_single_phone_with_formatting(original_val, seed: int, normalize_phone: bool = False, keep_anomalies: bool = False) -> str:
    if original_val is None:
        return None
    phone_str = str(original_val).strip()
    if phone_str == "" or phone_str.lower() in {"none", "null", "<null>"}:
        return None
    clean_digits = re.sub(r"[^0-9]", "", phone_str)

    if keep_anomalies:
        if not (_PHONE_RE.match(phone_str) and 7 <= len(clean_digits) <= 15):
            return phone_str

    def local_digits_hash(val: str, digit_count: int) -> str:
        hashed = hashlib.md5((val + "FabricPhoneMasking2026_v1" + str(seed)).encode("utf-8")).hexdigest()
        entropy_val = int(hashed[:15], 16)
        return str(entropy_val % (10 ** digit_count)).zfill(digit_count)

    def local_fallback_mobile(val: str) -> str:
        hashed = hashlib.md5((val + "FabricPhoneMasking2026_v1" + str(seed)).encode("utf-8")).hexdigest()
        entropy_val = int(hashed[:15], 16)
        first_digit = str((entropy_val % 4) + 6)
        suffix_digits = str((entropy_val // 10) % 1000000000).zfill(9)
        return first_digit + suffix_digits

    if clean_digits in {"100", "101", "108", "112", "1930", "155260"}:
        return phone_str

    if clean_digits.startswith("1800") or clean_digits.startswith("1860"):
        if len(clean_digits) >= 7:
            suffix_len = len(clean_digits) - 4
            replacement = clean_digits[:4] + local_digits_hash(clean_digits, suffix_len)
            return replacement if normalize_phone else rebuild_with_format(phone_str, replacement)

    if clean_digits.startswith("140") or clean_digits.startswith("160"):
        if len(clean_digits) >= 6:
            suffix_len = len(clean_digits) - 3
            replacement = clean_digits[:3] + local_digits_hash(clean_digits, suffix_len)
            return replacement if normalize_phone else rebuild_with_format(phone_str, replacement)

    std_codes = ["08564", "0866", "0861", "0870", "0877", "040", "022", "033", "044", "080", "020", "079"]
    matched_std = None
    for std in sorted(std_codes, key=len, reverse=True):
        if clean_digits.startswith(std):
            matched_std = std
            break

    if matched_std is not None and len(clean_digits) > len(matched_std):
        suffix_len = len(clean_digits) - len(matched_std)
        replacement = matched_std + local_digits_hash(clean_digits, suffix_len)
        return replacement if normalize_phone else rebuild_with_format(phone_str, replacement)

    normalized_mobile = None
    mobile_prefix_style = None

    if len(clean_digits) == 13 and clean_digits.startswith("091") and clean_digits[3] in "6789":
        normalized_mobile = clean_digits[3:]
        mobile_prefix_style = "091"
    elif len(clean_digits) == 12 and clean_digits.startswith("91") and clean_digits[2] in "6789":
        normalized_mobile = clean_digits[2:]
        mobile_prefix_style = "91"
    elif len(clean_digits) == 11 and clean_digits.startswith("0") and clean_digits[1] == "9" and clean_digits[2] in "6789":
        normalized_mobile = clean_digits[1:]
        mobile_prefix_style = "0"
    elif len(clean_digits) == 10 and clean_digits[0] in "6789":
        normalized_mobile = clean_digits
        mobile_prefix_style = ""

    if normalized_mobile is not None:
        masked_mobile = normalized_mobile[0] + local_digits_hash(normalized_mobile, 9)
        if normalize_phone:
            return masked_mobile
        else:
            if mobile_prefix_style == "091": replacement = "091" + masked_mobile
            elif mobile_prefix_style == "91": replacement = "91" + masked_mobile
            elif mobile_prefix_style == "0": replacement = "0" + masked_mobile
            else: replacement = masked_mobile
            return rebuild_with_format(phone_str, replacement)

    return local_fallback_mobile(phone_str)

def _vectorized_phone_masker(col_expr: pl.Expr, seed: int, normalize_phone: bool = False, keep_anomalies: bool = False) -> pl.Expr:
    return (
        pl.when(
            col_expr.is_null()
            | (col_expr.cast(pl.String).str.strip_chars() == "")
            | (col_expr.cast(pl.String).str.to_lowercase() == "none")
            | (col_expr.cast(pl.String).str.to_lowercase() == "null")
        )
        .then(None)
        .otherwise(
            col_expr.map_elements(
                lambda v, s=seed, np=normalize_phone, ka=keep_anomalies: _mask_single_phone_with_formatting(v, s, np, ka),
                return_dtype=pl.String
            )
        )
    )

# ==============================================================================
# 5. ROBUST AUTO-DETECTING DATE MASKING WITH OUTPUT FORMAT SUPPORT
# ==============================================================================
def parse_date_safely(value_str: str):
    s = str(value_str).strip()
    for _, info in SUPPORTED_DATE_FORMATS.items():
        try:
            return datetime.datetime.strptime(s, info["pattern"]).date()
        except ValueError:
            continue
    return None

def _mask_date_value(value, seed: int, target_format_selection: str):
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in ("none", "null"):
        return None

    parsed_date = None
    matched_pattern = "%d-%m-%Y"
    for _, info in SUPPORTED_DATE_FORMATS.items():
        try:
            parsed_date = datetime.datetime.strptime(s, info["pattern"]).date()
            matched_pattern = info["pattern"]
            break
        except ValueError:
            continue

    h = int(hashlib.md5((s + "DateMasking2026_v1" + str(seed)).encode("utf-8")).hexdigest(), 16)

    if parsed_date is None:
        parsed_date = datetime.date(1985, 1, 1) + datetime.timedelta(days=h % 12000)

    raw_mod = h % 372
    shift_days = (raw_mod - 365) if raw_mod < 186 else ((raw_mod - 186) + 180)
    new_date = parsed_date + datetime.timedelta(days=shift_days)

    if target_format_selection == "Original Format":
        out_pattern = matched_pattern
    else:
        out_pattern = SUPPORTED_DATE_FORMATS.get(target_format_selection, {}).get("pattern", "%d-%m-%Y")

    return new_date.strftime(out_pattern)

# ==============================================================================
# 6. UNIVERSAL COLUMN ANOMALY INSPECTOR
# ==============================================================================
def inspect_column_datatype_anomalies(df: pl.DataFrame, col: str, algo: str) -> tuple[list, bool]:
    try:
        sample_vals = df[col].drop_nulls().head(2000).cast(pl.Utf8, strict=False).to_list()
        cleaned = [str(v).strip() for v in sample_vals if v is not None and str(v).strip() not in ("", "none", "null")]
        if not cleaned:
            return [], False

        clean_algo = algo.upper().replace(" ", "").replace("-", "")

        if any(k in clean_algo for k in ["DATE", "DOB"]):
            formats_found = []
            for v in cleaned:
                matched = False
                for f_name, info in SUPPORTED_DATE_FORMATS.items():
                    try:
                        datetime.datetime.strptime(v, info["pattern"])
                        formats_found.append(f_name)
                        matched = True
                        break
                    except ValueError:
                        continue
                if not matched:
                    formats_found.append("Custom/Unknown")
            uniq_fmts = sorted(list(set(formats_found)))
            return uniq_fmts, len(uniq_fmts) > 1

        elif any(k in clean_algo for k in ["NUMBER", "NUMERICAL", "BUCKET"]):
            non_numeric_types = set()
            for v in cleaned:
                if not _NUMERIC_RE.match(v):
                    non_numeric_types.add("Text String")
            if non_numeric_types:
                return list(non_numeric_types) + ["Numeric"], True
            return ["Numeric"], False

        elif "EMAIL" in clean_algo:
            invalid = sum(1 for v in cleaned if not _EMAIL_RE.match(v)) > 0
            return (["Non-Standard Email", "Standard Email"], True) if invalid else (["Standard Email"], False)

        elif any(k in clean_algo for k in ["PHONE", "CONTACT"]):
            def _digits(v): return sum(ch.isdigit() for ch in v)
            non_phone_count = sum(1 for v in cleaned if not (_PHONE_RE.match(v) and 7 <= _digits(v) <= 15))
            has_anomalies = non_phone_count > 0
            detected_types = []
            if has_anomalies:
                detected_types.append("Text/Mixed Data")
            detected_types.append("Phone Format")
            return detected_types, has_anomalies

        return [], False
    except Exception:
        return [], False

# ==============================================================================
# 7. CORE VECTORIZED EXPRESSION ROUTER
# ==============================================================================
def get_vectorized_expression(
    col: str,
    algo: str,
    seed: int = DEFAULT_SEED,
    match_names: bool = False,
    df_cols: list = None,
    normalize_phone: bool = False,
    target_date_format: str = "Original Format",
    keep_anomalies: bool = False,
    rules_dict: dict = None,
    active_table: str = ""
) -> pl.Expr:
    algo_clean = re.sub(r"[^A-Z]", "", str(algo).upper())
    col_expr = pl.col(col)

    is_null_or_empty = col_expr.is_null() | (col_expr.cast(pl.String).str.strip_chars() == "")

    if algo_clean in ["FIRSTNAME", "NAMEFIRST", "FIRSTNAMEANONYMIZATION"]:
        return pl.when(is_null_or_empty).then(None).otherwise(_generate_first_name_from_expr(col_expr, seed))

    elif algo_clean in ["LASTNAME", "NAMELAST", "LASTNAMEANONYMIZATION"]:
        return pl.when(is_null_or_empty).then(None).otherwise(_generate_last_name_from_expr(col_expr, seed))

    elif algo_clean in ["FULLNAME", "NAMEFULL", "FULLNAMEANONYMIZATION"]:
        return pl.when(is_null_or_empty).then(None).otherwise(_generate_exact_full_name_from_expr(col_expr, seed))

    elif algo_clean in ["NUMBER", "NUMERICAL", "NUMBERS"]:
        # Dynamically calculate varying numeric values derived from row text/hash & seed
        entropy = _get_string_entropy_expr(col_expr, "FabricAmountMasking2026_v1", seed)
        gen_float = ((entropy % 950000) + 105.7) / 100.0
        return pl.when(is_null_or_empty).then(None).otherwise(gen_float)

    elif algo_clean == "EMAIL":
        return pl.when(col_expr.is_null()).then(None).otherwise(
            _vectorized_email_masker(
                col_expr, seed,
                match_names=match_names,
                rules_dict=rules_dict,
                active_table=active_table,
                df_cols=df_cols
            )
        )

    elif algo_clean in ["PHONENUMBER", "CONTACT", "PHONENUMBERANONYMIZATION"]:
        return (
            pl.when(is_null_or_empty)
            .then(None)
            .otherwise(_vectorized_phone_masker(col_expr, seed, normalize_phone=normalize_phone, keep_anomalies=keep_anomalies))
        )

    elif algo_clean == "ALPHANUMERIC":
        str_expr = col_expr.cast(pl.String).fill_null("NULL")
        masked_expr = (
            str_expr.str.split("")
            .list.eval(
                pl.element().hash(seed=seed)
                .pipe(lambda h:
                    pl.when(pl.element().str.contains(r"[A-Z]")).then(pl.lit(UPPER_ALPHABET).list.get((h % 26).cast(pl.UInt32)))
                    .when(pl.element().str.contains(r"[a-z]")).then(pl.lit(LOWER_ALPHABET).list.get((h % 26).cast(pl.UInt32)))
                    .when(pl.element().str.contains(r"[0-9]")).then(pl.lit(DIGITS_POOL).list.get((h % 10).cast(pl.UInt32)))
                    .otherwise(pl.element())
                )
            ).list.join("")
        )
        return pl.when(col_expr.is_null()).then(None).otherwise(masked_expr)

    elif algo_clean in ["DATETYPE", "DOB", "DATE"]:
        return (
            pl.when(is_null_or_empty)
            .then(None)
            .otherwise(
                col_expr.map_elements(
                    lambda v, s=seed, tf=target_date_format: _mask_date_value(
                        v, seed=s, target_format_selection=tf
                    ),
                    return_dtype=pl.String
                )
            )
        )

    elif algo_clean in ["BUCKETBASED", "BUCKET"]:
        entropy = _get_string_entropy_expr(col_expr, "FabricBucketMasking2026_v1", seed)
        candidate = (10 + (entropy % 90)).cast(pl.Int64)
        return pl.when(col_expr.is_null()).then(None).otherwise(candidate.cast(pl.String))

    return col_expr

def infer_field_datatype(sample_values) -> str:
    cleaned = [str(v).strip() for v in sample_values if v is not None and str(v).strip() != ""]
    if not cleaned:
        return "Text"
    total = len(cleaned)
    if sum(1 for v in cleaned if _EMAIL_RE.match(v)) / total >= 0.7:
        return "Email"
    if sum(1 for v in cleaned if parse_date_safely(v) is not None) / total >= 0.7:
        return "Date"
    numeric_count = sum(1 for v in cleaned if _NUMERIC_RE.match(v))
    if numeric_count / total >= 0.7:
        return "Number"
    return "Text"