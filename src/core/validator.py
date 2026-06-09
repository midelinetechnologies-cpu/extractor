import re
from src.utils.constants import EMAIL_REGEX, URL_REGEX


def is_valid_email(value: str) -> bool:
    return bool(re.fullmatch(EMAIL_REGEX, value.strip(), re.IGNORECASE))


def is_valid_url(value: str) -> bool:
    return bool(re.fullmatch(URL_REGEX, value.strip(), re.IGNORECASE))
