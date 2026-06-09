import re
import streamlit as st
from src.utils.constants import EMAIL_REGEX, URL_REGEX, PHONE_REGEX

_NAME_PATTERN = re.compile(r'\b([A-Z][a-z]{1,15}(?:\s[A-Z][a-z]{1,15}){1,2})\b')
_NAME_SKIP = {
    'The', 'This', 'That', 'These', 'Hello', 'Dear', 'From', 'To',
    'Subject', 'Best', 'Kind', 'Warm', 'With', 'Please', 'Thank',
    'Regards', 'Sincerely', 'Hi', 'Hey',
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
    'January', 'February', 'March', 'April', 'June', 'July', 'August',
    'September', 'October', 'November', 'December',
    'Sales', 'Email', 'Phone', 'Contact', 'Contacts', 'Google', 'Bing',
    'Help', 'Support', 'Center', 'Account', 'Community', 'Database',
    'Network', 'Service', 'Services', 'Career', 'Growth', 'Excel',
    'Text', 'File', 'Free', 'Name', 'Roll', 'Student', 'Employee',
    'Code', 'India', 'Indian', 'Automotive', 'Navigator', 'Spreadsheet',
    'Directory', 'Provider', 'Resume', 'Number', 'Numbers', 'Profile',
    'Search', 'Results', 'Data', 'List', 'Export', 'Import', 'Linkedin',
    'Twitter', 'Facebook', 'Instagram', 'Youtube', 'Microsoft', 'Apple',
    'Institute', 'College', 'University', 'School', 'Academy',
    'Department', 'Division', 'Office', 'Bureau', 'Ministry',
    'Company', 'Corporation', 'Limited', 'Private',
    'New', 'Old', 'First', 'Last', 'Next', 'Previous',
    'Id', 'Ids', 'Pdf', 'Csv', 'Doc',
}


def extract_names_heuristic(text: str) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for name in _NAME_PATTERN.findall(text):
        if name.split()[0] not in _NAME_SKIP and name not in seen:
            seen.add(name)
            results.append(name)
    return results


@st.cache_resource
def get_extractor() -> "Extractor":
    return Extractor()


@st.cache_resource
def _load_nlp():
    try:
        import spacy
        return spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        return None


def nlp_available() -> bool:
    return _load_nlp() is not None


class Extractor:
    def __init__(self) -> None:
        self._email_re = re.compile(EMAIL_REGEX, re.IGNORECASE)
        self._url_re = re.compile(URL_REGEX, re.IGNORECASE)
        self._phone_re = re.compile(PHONE_REGEX)

    def extract_emails(self, text: str, dedupe: bool = True) -> list[str]:
        found = self._email_re.findall(text)
        if dedupe:
            found = list(dict.fromkeys(v.lower() for v in found))
        return found

    def extract_urls(self, text: str, dedupe: bool = True) -> list[str]:
        email_domains = {m.split("@")[1].lower().rstrip(".") for m in self._email_re.findall(text)}
        found = [u for u in self._url_re.findall(text) if u.lower().rstrip("/").rstrip(".") not in email_domains]
        if dedupe:
            found = list(dict.fromkeys(found))
        return found

    def extract_phones(self, text: str, dedupe: bool = True) -> list[str]:
        found = self._phone_re.findall(text)
        if dedupe:
            found = list(dict.fromkeys(found))
        return found

    def extract_names(self, text: str, dedupe: bool = True) -> list[str]:
        seen: set[str] = set()
        results = extract_names_heuristic(text)
        seen.update(results)
        nlp = _load_nlp()
        if nlp is not None:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    name = ent.text.strip()
                    if name not in seen:
                        seen.add(name)
                        results.append(name)
        return results

    def extract_orgs(self, text: str, dedupe: bool = True) -> list[str]:
        nlp = _load_nlp()
        if nlp is None:
            return []
        doc = nlp(text)
        found = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
        if dedupe:
            found = list(dict.fromkeys(found))
        return found
