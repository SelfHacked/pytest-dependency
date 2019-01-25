STR_FALSE = ["0", "no", "n", "false", "f", "off"]
STR_TRUE = ["1", "yes", "y", "true", "t", "on"]


def str_to_bool(value):
    """
    Evaluate string representation of a boolean value.
    """
    if not value:
        return False
    if value.lower() in STR_FALSE:
        return False
    if value.lower() in STR_TRUE:
        return True
    raise ValueError("Invalid truth value '%s'" % value)
