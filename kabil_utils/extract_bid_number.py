import re

PREFIXES = r"(?:BID|RFP|RFQ|RFQual\w*|RFI|RFB|ITB|IFB|IFQ|ITQ|SOLICITATION|PROPOSAL|QUOTE|FP|DPW|SI-CUCF|PON|Bid|RFQu|(?-i:OF))"
LABEL = rf"(?:{PREFIXES}\b\s*(?:NO\.?|NUMBER|#)?\s*[:#\-]?\s*)?"

# A segment must contain a digit, OR be 1-4 letters followed by a segment with a digit (e.g. "BT" in 20-BT-026)
SEG = r"(?=[A-Z\d]*\d|[A-Z]{1,4}[-/.][A-Z\d]*\d)[A-Z\d]+"

NUM = rf"[A-Z]{{0,4}}\d[A-Z\d]*(?:[-/.]{SEG})*"

LEADING_RE = re.compile(rf"^\s*({LABEL}{NUM})", re.I)

PREFIXED_RE = re.compile(
    rf"(?<![\w/])([A-Z]{{1,5}}-\d{{2,4}}(?:[-.]{SEG})+)(?![\w/])",
    re.I,
)

ANYWHERE_RE = re.compile(
    rf"(?<![\w/])({LABEL}[A-Z]{{0,4}}\d{{2,4}}(?:[-.]{SEG})+)(?![\w/])",
    re.I,
)

def extract_bid_no(bid_title: str) -> str:
    title = re.sub(r"\s+", " ", bid_title.replace("\xa0", " ")).strip()

    m = LEADING_RE.match(title) or PREFIXED_RE.search(title) or ANYWHERE_RE.search(title)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).rstrip(".-/ ")

    return title[:25].strip()