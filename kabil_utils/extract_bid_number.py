import re

PREFIXES = r"(?:BID|RFP|RFQ|RFQual\w*|RFI|RFB|ITB|IFB|IFQ|ITQ|SOLICITATION|PROPOSAL|QUOTE)"
LABEL = rf"(?:{PREFIXES}\b\s*(?:NO\.?|NUMBER|#)?\s*[:#\-]?\s*)?"   # optional prefix, kept in the result

# 1) number at the start: "RFP 26-01F ...", "BID 2026-0010 ...", "CC26-472RE ...", "Bid#26-213-07"
LEADING_RE = re.compile(
    rf"^\s*({LABEL}[A-Z]{{0,4}}\d[\w\-/.]*)",
    re.I,
)

# 2) number anywhere: "... Management 2027-02", "... RFP 26-01 ..."
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