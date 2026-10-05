import re

MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

DATE_RE = re.compile(rf"\b{MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.I)

def extract_raw_date(text: str, default: str = "") -> str:
    text = re.sub(r"\s+", " ", text.replace("\xa0", " "))
    m = DATE_RE.search(text)               
    return m.group(0) if m else default