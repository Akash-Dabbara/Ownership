import random

import polars as pl

from app.anonymization.algorithms import (
    DEFAULT_SEED,
    get_vectorized_expression,
)

# Algorithms whose output is alphabetic text, where a casing
# choice (UPPERCASE/lowercase/Title Case) makes sense. Matches
# the frontend's TEXT_ALGORITHMS set in FilePreview.jsx.
TEXT_ALGORITHM_KEYS = {
    "FIRSTNAME",
    "LASTNAME",
    "FULLNAME",
    "EMAIL",
    "ALPHANUMERIC",
}


def _to_jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def anonymize_dataset(
    columns: list[str],
    rows: list[list],
    column_rules: dict,
) -> dict:
    """
    Applies the configured algorithm/casing/consistency rules to
    a full dataset (columns + rows already read from the source),
    using the vectorized expressions in algorithms.py.

    column_rules: {
        "column_name": {
            "algorithm": "FIRST_NAME" | "EMAIL" | ... ,
            "casing": "ORIGINAL" | "UPPERCASE" | "lowercase" | "Title Case",
            "consistency": bool,
        },
        ...
    }

    Columns with no rule (or algorithm == "") are left unchanged.
    """

    if not rows:
        return {"columns": columns, "rows": []}

    df = pl.DataFrame(
        rows,
        schema=columns,
        orient="row",
        strict=False,
    )

    select_exprs = []

    for col in columns:
        rule = column_rules.get(col)

        if not rule or not rule.get("algorithm"):
            select_exprs.append(pl.col(col))
            continue

        algorithm = rule["algorithm"]
        consistency = bool(rule.get("consistency", False))
        casing = rule.get("casing", "ORIGINAL")

        # Consistency: same seed every run == same output every run,
        # forever. Without it, a fresh random seed each run means
        # the output will differ from run to run.
        seed = DEFAULT_SEED if consistency else random.randint(1, 2_000_000_000)

        expr = get_vectorized_expression(
            col=col,
            algo=algorithm,
            seed=seed,
            df_cols=columns,
        ).alias(col)

        algo_key = algorithm.upper().replace(" ", "").replace("_", "")

        if algo_key in TEXT_ALGORITHM_KEYS:
            if casing == "UPPERCASE":
                expr = expr.str.to_uppercase()
            elif casing == "lowercase":
                expr = expr.str.to_lowercase()
            elif casing == "Title Case":
                expr = expr.str.to_titlecase()

        select_exprs.append(expr)

    anonymized_df = df.select(select_exprs)

    return {
        "columns": anonymized_df.columns,
        "rows": [
            [_to_jsonable(value) for value in row]
            for row in anonymized_df.rows()
        ],
    }