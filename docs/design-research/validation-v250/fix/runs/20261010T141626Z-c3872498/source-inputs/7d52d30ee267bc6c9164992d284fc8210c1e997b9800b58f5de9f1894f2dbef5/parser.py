def parse_bool(text):
    value = text.strip().lower()
    if value == "true": return True
    if value == "false": return False
    raise ValueError("invalid boolean")
