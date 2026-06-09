EMAIL_REGEX = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"

VALID_TLDS = {
    "com", "net", "org", "edu", "gov", "io", "co", "in", "uk", "us", "au",
    "ca", "de", "fr", "jp", "cn", "ru", "br", "mx", "es", "it", "nl", "se",
    "no", "fi", "dk", "be", "ch", "at", "nz", "sg", "hk", "info", "biz",
    "tv", "me", "app", "dev", "ai", "tech", "online", "store", "site", "web",
}
_PATH = r"(?:/[-\w._~:/?#\[\]@!$&'()*+,;%=]*)?"
_TLD = r"(?:com|co|in|net|org|io|edu|gov|uk|us|au|ca|de|fr|info|biz)"

URL_REGEX = (
    r"(?:"
    # Full URLs with protocol
    r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+" + _PATH +
    r"|"
    # www. prefix without protocol
    r"www\.[-\w]{2,}(?:\.[-\w]{2,})*\." + _TLD + _PATH +
    r"|"
    # Bare domains — negative lookbehind for @ to avoid matching email hosts
    r"(?<!@)(?<!\.)\b[-\w]{2,}(?:\.[-\w]{2,})*\." + _TLD + _PATH +
    r")"
)
PHONE_REGEX = (
    r"(?:"
    # International with + prefix: +91 7669945117, +1-800-555-0100
    r"\+\d{1,3}[-.\s]?\(?\d{1,5}\)?(?:[-.\s]?\d{1,5}){1,4}"
    r"|"
    # US format: optional +1, (NXX) NXX-XXXX
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"
    r"|"
    # South/South-East Asian 10-digit mobile starting with 6-9
    r"(?<![+\d])[6-9]\d{9}(?!\d)"
    r"|"
    # 0-prefix landlines: 0772981033, 011-XXXXXXXX
    r"(?<!\d)0\d{9,10}(?!\d)"
    r")"
)

SEPARATORS: dict[str, str] = {
    "New Line": "\n",
    "Comma": ", ",
    "Semicolon": "; ",
    "And": " and ",
    "Space": " ",
    "Pipe": " | ",
    "Tab": "\t",
}

OUTPUT_FORMATS = [
    "Select Output Format",
    "Only Email",
    "Website + Email",
    "Name + Website + Email",
    "Name + Website + Email + Phone",
]

# Which DataFrame columns to show per format
FORMAT_COLUMNS: dict[str, list[str]] = {
    "Only Email":                    ["Emails"],
    "Website + Email":               ["URLs", "Emails"],
    "Name + Website + Email":        ["Name", "URLs", "Emails"],
    "Name + Website + Email + Phone":["Name", "URLs", "Emails", "Phones"],
}
EXTRACTION_TYPES = [ "All"]
