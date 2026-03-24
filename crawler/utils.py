"""
Utility functions for the web crawler.
- URL normalization (strip fragments, trailing slashes, sort params)
- Text extraction from HTML
- Domain extraction for rate limiting
"""

from urllib.parse import urlparse, urlunparse, urljoin, parse_qs, urlencode
import re


def normalize_url(url: str, base_url: str = "") -> str:
    """Normalize a URL for deduplication.

    - Resolve relative URLs against base_url
    - Strip fragments (#section)
    - Remove trailing slashes from path
    - Sort query parameters
    - Lowercase scheme and host
    """
    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    # Only crawl http/https
    if parsed.scheme not in ("http", "https"):
        return ""

    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if not netloc:
        return ""

    # Remove default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Clean path
    path = parsed.path.rstrip("/") or "/"

    # Sort query params for consistency
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_query = urlencode(sorted(params.items()), doseq=True)
    else:
        sorted_query = ""

    # Reconstruct without fragment
    normalized = urlunparse((scheme, netloc, path, parsed.params, sorted_query, ""))
    return normalized


def extract_domain(url: str) -> str:
    """Extract the domain (netloc) from a URL."""
    parsed = urlparse(url)
    return parsed.netloc.lower()


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract and normalize all <a href> links from HTML.
    Uses regex instead of BeautifulSoup for lightweight link extraction.
    """
    links = set()
    # Find all href attributes
    href_pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)
    for match in href_pattern.finditer(html):
        href = match.group(1).strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        normalized = normalize_url(href, base_url)
        if normalized:
            links.add(normalized)
    return list(links)


def extract_text(html: str) -> str:
    """Extract visible text content from HTML, stripping tags and collapsing whitespace."""
    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode common HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_title(html: str) -> str:
    """Extract the <title> from HTML."""
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()
        # Clean up whitespace inside title
        title = re.sub(r'\s+', ' ', title)
        return title
    return ""


def is_valid_crawl_url(url: str) -> bool:
    """Check if a URL is valid for crawling (not a binary file, etc.)."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    # Skip common binary/non-HTML extensions
    skip_extensions = {
        '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico',
        '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
        '.zip', '.tar', '.gz', '.rar', '.7z',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv',
        '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.exe', '.dmg', '.bin', '.iso',
    }

    for ext in skip_extensions:
        if path.endswith(ext):
            return False

    return True
