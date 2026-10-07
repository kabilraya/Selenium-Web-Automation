import re

PREFIXES = r"(?:BID|RFP|RFQ|RFQual\w*|RFI|RFB|ITB|IFB|IFQ|ITQ|SOLICITATION|PROPOSAL|QUOTE | FP)"
LABEL = rf"(?:{PREFIXES}\b\s*(?:NO\.?|NUMBER|#)?\s*[:#\-]?\s*)?"   # optional prefix, kept in the result


LEADING_RE = re.compile(
    rf"^\s*({LABEL}[A-Z]{{0,4}}\d[\w\-/.]*)",
    re.I,
)


ANYWHERE_RE = re.compile(
    rf"(?<![\w/])({LABEL}[A-Z]{{0,4}}\d{{2,4}}(?:-[A-Z0-9]+)+)(?![\w/])",
    re.I,
)

def extract_bid_no(bid_title: str) -> str:
    title = re.sub(r"\s+", " ", bid_title.replace("\xa0", " ")).strip()

    m = LEADING_RE.match(title) or ANYWHERE_RE.search(title)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).rstrip(".-/ ")

    return title[:25].strip()          # no number found, fall back to the start of the title