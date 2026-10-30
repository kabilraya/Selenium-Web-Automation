import re

PREFIXES = r"(?:BID|RFP|RFQ|RFQual\w*|RFI|RFB|ITB|IFB|IFQ|ITQ|SOLICITATION|PROPOSAL|QUOTE|FP|DPW|SI-CUCF|PON|Bid|(?-i:OF))"
LABEL = rf"(?:{PREFIXES}\b\s*(?:NO\.?|NUMBER|#)?\s*[:#\-]?\s*)?"

NUM = r"[A-Z]{0,4}\d[A-Z\d]*(?:[-/.](?=[A-Z\d]*\d)[A-Z\d]+)*"

LEADING_RE = re.compile(rf"^\s*({LABEL}{NUM})", re.I)

# NEW: letter-code prefix + hyphen, e.g. PS-2026-03, ED-2026-01
PREFIXED_RE = re.compile(
    r"(?<![\w/])([A-Z]{1,5}-\d{2,4}(?:[-.](?=[A-Z\d]*\d)[A-Z\d]+)+)(?![\w/])",
    re.I,
)

ANYWHERE_RE = re.compile(
    rf"(?<![\w/])({LABEL}[A-Z]{{0,4}}\d{{2,4}}(?:[-.](?=[A-Z\d]*\d)[A-Z\d]+)+)(?![\w/])",
    re.I,
)

def extract_bid_no(bid_title: str) -> str:
    title = re.sub(r"\s+", " ", bid_title.replace("\xa0", " ")).strip()

    m = LEADING_RE.match(title) or PREFIXED_RE.search(title) or ANYWHERE_RE.search(title)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).rstrip(".-/ ")

    return title[:25].strip()