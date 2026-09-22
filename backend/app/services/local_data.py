import os
from urllib.parse import urlparse

import pandas as pd

UPLOAD_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "storage",
    "uploads",
)

EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}

# The ZIP file signature every .xlsx (and .docx, .pptx, etc.) file
# starts with. Used as a safety net when the extension is missing
# or wrong, so a misnamed Excel file still gets read correctly
# instead of being fed to the CSV parser as garbage binary text.
ZIP_MAGIC_BYTES = b"PK\x03\x04"


def _to_jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def ensure_upload_storage_dir() -> str:
    os.makedirs(UPLOAD_STORAGE_DIR, exist_ok=True)
    return UPLOAD_STORAGE_DIR


def _get_extension(source_path: str) -> str:
    """
    Extracts a lowercase file extension from either a local file
    path or a URL (stripping any query string first).
    """

    path_only = urlparse(source_path).path or source_path
    return os.path.splitext(path_only)[1].lower()


def _looks_like_excel_local_file(source_path: str) -> bool:
    """
    Reads the first few bytes of a local file to check for the
    ZIP signature that every .xlsx file starts with — a safety
    net for files with a missing or incorrect extension.
    """

    try:
        with open(source_path, "rb") as f:
            header = f.read(4)
        return header == ZIP_MAGIC_BYTES
    except Exception:
        return False


def _read_excel(source, nrows: int):
    return pd.read_excel(source, nrows=nrows, engine="openpyxl")


def _read_csv_with_encoding_fallback(source, nrows: int):
    """
    Tries a sequence of (encoding, delimiter) combinations, since:
      - CSVs exported from Excel on Windows are very often
        Windows-1252, not UTF-8.
      - Many "CSV" exports (especially European Excel locales)
        actually use ';' or a tab character, not a comma.

    Explicit delimiters are tried in priority order rather than
    relying on pandas' automatic sniffer, since the sniffer can
    misfire on files with commas/semicolons embedded inside text
    fields (producing a wildly wrong field count, e.g. "expected
    X fields, saw Y").

    As an absolute last resort, malformed rows are skipped rather
    than failing the whole read, so a preview is still possible
    even if a handful of rows in the source file are genuinely
    inconsistent.
    """

    encodings_to_try = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    delimiters_to_try = [",", ";", "\t", "|"]
    last_error = None

    for encoding in encodings_to_try:
        for delimiter in delimiters_to_try:
            try:
                df = pd.read_csv(
                    source,
                    nrows=nrows,
                    encoding=encoding,
                    sep=delimiter,
                )
                if df.shape[1] > 1 or delimiter == delimiters_to_try[-1]:
                    return df
            except Exception as exc:
                last_error = exc
            finally:
                if hasattr(source, "seek"):
                    source.seek(0)

    try:
        if hasattr(source, "seek"):
            source.seek(0)
        return pd.read_csv(
            source,
            nrows=nrows,
            encoding="latin-1",
            encoding_errors="replace",
            sep=",",
            engine="python",
            on_bad_lines="skip",
        )
    except Exception:
        raise last_error


def read_local_or_url_data(source_path: str, limit: int = 100) -> dict:
    """
    Reads data from either:
      - a public URL (source_path starts with http:// or https://)
      - a file stored on local server disk (any other path, which
        must live under UPLOAD_STORAGE_DIR)

    Detects whether the file is Excel (.xlsx/.xlsm/.xls) or CSV
    and reads it with the correct parser — feeding a raw Excel
    file (which is actually a ZIP archive internally) to the CSV
    parser produces unreadable binary garbage, which is what this
    fixes.

    No connector or credential is involved — this is used only
    for Workspaces with source_type URL or LOCAL_FILE, which have
    no login of any kind.
    """

    if not source_path:
        raise ValueError("Source path cannot be empty.")

    is_url = source_path.startswith("http://") or source_path.startswith("https://")

    if not is_url and not os.path.isfile(source_path):
        raise ValueError(f"Stored file was not found: {source_path}")

    extension = _get_extension(source_path)
    is_excel = extension in EXCEL_EXTENSIONS or (
        not is_url and _looks_like_excel_local_file(source_path)
    )

    try:
        if is_excel:
            df = _read_excel(source_path, nrows=limit)
        else:
            df = _read_csv_with_encoding_fallback(source_path, nrows=limit)

        df = df.astype(object).where(pd.notnull(df), None)

        rows = [
            [_to_jsonable(value) for value in row]
            for row in df.values.tolist()
        ]

        return {
            "columns": [str(c) for c in df.columns],
            "rows": rows,
        }
    except Exception as exc:
        raise ValueError(f"Unable to read data: {str(exc)}") from exc