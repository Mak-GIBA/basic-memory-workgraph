def parse_bool(text):
    value = text.lower()
    if value == "true": return True
    if value == "false": return False
    raise ValueError("invalid boolean")
