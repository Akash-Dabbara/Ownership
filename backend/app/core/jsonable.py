def to_jsonable(value):
    """
    Converts a single database cell value into something JSON
    can represent. Dates, Decimals, UUIDs, etc. become strings;
    plain str/int/float/bool/None pass through unchanged.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)