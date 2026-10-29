import re

MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

DATE_RE = re.compile(
    rf"\b{MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}}\b", re.I
)

def extract_raw_date(text: str, default: str = "") -> str:
    text = re.sub(r"\s+", " ", text.replace("\xa0", " "))
    m = DATE_RE.search(text)
    if not m:
        return default
    date = m.group(0)
    # "February 25,2026" -> "February 25, 2026"
    return re.sub(r",\s*(?=\d{4})", ", ", date)