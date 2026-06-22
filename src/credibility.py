from urllib.parse import urlparse


def compute_credibility_score(url: str, title: str = "") -> int:
    """
    Computes a source credibility score (0-100) based on domain authority
    and publication source indicators.
    """
    if not url:
        return 50  # Neutral baseline

    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()

    # Strip www.
    if domain.startswith("www."):
        domain = domain[4:]

    # Rule 1: Peer-reviewed academic preprint / academic graph databases (highest trust)
    top_academic = [
        "arxiv.org", "semanticscholar.org", "api.semanticscholar.org"
    ]
    if any(ta in domain for ta in top_academic):
        return 98

    # Rule 2: Government (.gov)
    if domain.endswith(".gov") or domain.endswith(".gov.uk") or domain.endswith(".gov.in"):
        return 95

    # Rule 3: Academic (.edu, .ac.uk, etc.)
    if domain.endswith(".edu") or domain.endswith(".ac.uk") or domain.endswith(".edu.in"):
        return 92

    # Rule 4: Known Scientific / Academic publishing domains
    academic_domains = [
        "nature.com", "ieee.org", "springer.com", "science.org",
        "sciencedirect.com", "researchgate.net", "scholar.google.com",
        "academia.edu", "acm.org", "doi.org"
    ]
    if any(ad in domain for ad in academic_domains):
        return 90

    # Rule 5: Known Tech/Industry Leaders & Standards Bodies
    tech_authoritative = [
        "nist.gov", "ietf.org", "w3.org", "rfc-editor.org", "iso.org",
        "ibm.com", "microsoft.com", "google.com", "aws.amazon.com",
        "intel.com", "oracle.com", "github.com"
    ]
    if any(ta in domain for ta in tech_authoritative):
        return 85

    # Rule 6: Reputable News Outlets
    news_outlets = [
        "reuters.com", "bloomberg.com", "apnews.com", "nytimes.com",
        "wsj.com", "ft.com", "economist.com", "bbc.co.uk", "bbc.com",
        "theguardian.com", "guardian.co.uk"
    ]
    if any(no in domain for no in news_outlets):
        return 80

    # Rule 7: General Tech Blogs / Media
    tech_blogs = [
        "techcrunch.com", "wired.com", "arstechnica.com", "venturebeat.com",
        "medium.com", "substack.com", "dev.to", "hackernoon.com"
    ]
    if any(tb in domain for tb in tech_blogs):
        return 50

    # Rule 8: Wikipedia — useful but community-edited, lower trust
    if "wikipedia.org" in domain:
        return 40

    # Rule 9: Basic generic commercial domains
    if domain.endswith(".com") or domain.endswith(".org") or domain.endswith(".net") or domain.endswith(".io"):
        return 65

    # Default baseline
    return 45
