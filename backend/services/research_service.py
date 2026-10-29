import logging
import ipaddress
import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

logger = logging.getLogger("lead_research")

_TIMEOUT = 6.0
_MAX_TOTAL_SECONDS = 12.0
_MAX_RESPONSE_BYTES = 512_000
_MAX_PAGE_CHARS = 1400
_MAX_CHARS = 5000
_MAX_PAGES = 3
_MAX_REDIRECTS = 3
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LeadResearchBot/1.0; "
        "+https://example.com/bot)"
    )
}

_WHITESPACE_RE = re.compile(r"\s+")
_RELEVANT_PAGE_RE = re.compile(
    r"about|company|product|platform|solution|service|industry|use-case|usecase",
    re.IGNORECASE,
)
_SKIP_TAGS = {"head", "script", "style", "noscript", "svg", "nav", "footer", "form"}


class _WebsiteHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.description = ""
        self.body_parts = []
        self.heading_parts = []
        self.links = []
        self._skip_depth = 0
        self._title_depth = 0
        self._heading_depth = 0
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "meta":
            name = (attributes.get("name") or attributes.get("property") or "").lower()
            if name in {"description", "og:description"} and not self.description:
                self.description = attributes.get("content", "")
        elif tag == "title":
            self._title_depth += 1
        elif tag in {"h1", "h2", "h3"}:
            self._heading_depth += 1
        elif tag == "a":
            self._anchor = {"href": attributes.get("href"), "text": []}

        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "title":
            self._title_depth = max(0, self._title_depth - 1)
        elif tag in {"h1", "h2", "h3"}:
            self._heading_depth = max(0, self._heading_depth - 1)
        elif tag == "a" and self._anchor is not None:
            self.links.append((self._anchor["href"], " ".join(self._anchor["text"])))
            self._anchor = None

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._title_depth:
            self.title_parts.append(text)
        if self._skip_depth:
            return
        self.body_parts.append(text)
        if self._heading_depth:
            self.heading_parts.append(text)
        if self._anchor is not None:
            self._anchor["text"].append(text)

    def parsed_page(self):
        clean = lambda parts: _WHITESPACE_RE.sub(" ", " ".join(parts)).strip()
        return {
            "title": clean(self.title_parts),
            "description": clean([self.description]),
            "body": clean(self.body_parts),
            "headings": clean(self.heading_parts),
            "links": self.links,
        }


def _normalize_url(url: str) -> str:
    value = url.strip()
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"
    try:
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        return ""

    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        return ""
    if parsed.username or parsed.password or (port is not None and port not in {80, 443}):
        return ""
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        return ""
    try:
        if not ipaddress.ip_address(hostname).is_global:
            return ""
    except ValueError:
        if re.fullmatch(r"[0-9.]+", hostname):
            return ""

    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, ""))


def _same_site(first_url: str, second_url: str) -> bool:
    first_host = (urlsplit(first_url).hostname or "").lower().removeprefix("www.")
    second_host = (urlsplit(second_url).hostname or "").lower().removeprefix("www.")
    return bool(first_host and first_host == second_host)


def _fetch_page(client: httpx.Client, url: str, deadline: float):
    current_url = url
    for redirect_count in range(_MAX_REDIRECTS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None

        with client.stream("GET", current_url, timeout=min(_TIMEOUT, remaining)) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location or redirect_count == _MAX_REDIRECTS:
                    return None
                next_url = _normalize_url(urljoin(current_url, location))
                if not next_url or not _same_site(current_url, next_url):
                    return None
                current_url = next_url
                continue

            if response.status_code >= 400:
                logger.info("Website fetch for %s returned %s; skipping.", current_url, response.status_code)
                return None
            content_type = response.headers.get("content-type", "").lower()
            if content_type and "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return None

            body = bytearray()
            for chunk in response.iter_bytes():
                remaining_bytes = _MAX_RESPONSE_BYTES - len(body)
                body.extend(chunk[:remaining_bytes])
                if len(body) >= _MAX_RESPONSE_BYTES or time.monotonic() >= deadline:
                    break
            encoding = response.encoding or "utf-8"

        parser = _WebsiteHTMLParser()
        parser.feed(bytes(body).decode(encoding, errors="replace"))
        parser.close()
        return current_url, parser.parsed_page()

    return None


def _relevant_links(page, page_url: str) -> list[str]:
    candidates = []
    seen = set()
    for href, label in page["links"]:
        if not href:
            continue
        target = _normalize_url(urljoin(page_url, href))
        if not target or not _same_site(page_url, target):
            continue
        path = urlsplit(target).path
        if not _RELEVANT_PAGE_RE.search(f"{path} {label}"):
            continue
        if target == page_url or target in seen:
            continue
        seen.add(target)
        candidates.append(target)
    return candidates


def fetch_website_research(url: str | None) -> dict | None:
    """
    Fetches the company homepage and up to two relevant same-site pages, then
    returns a bounded text summary and the URLs it came from.

    Best-effort only. Private/local address literals, unsafe redirects,
    oversized responses, non-HTML pages, and network failures are skipped.
    """
    if not url or not url.strip():
        return None

    normalized = _normalize_url(url)
    if not normalized:
        return None

    deadline = time.monotonic() + _MAX_TOTAL_SECONDS
    pending_urls = [normalized]
    visited_urls = set()
    fetched_pages = []
    try:
        with httpx.Client(follow_redirects=False, timeout=_TIMEOUT, headers=_HEADERS) as client:
            while pending_urls and len(fetched_pages) < _MAX_PAGES and time.monotonic() < deadline:
                page_url = pending_urls.pop(0)
                if page_url in visited_urls:
                    continue
                visited_urls.add(page_url)

                fetched = _fetch_page(client, page_url, deadline)
                if not fetched:
                    continue
                final_url, page = fetched
                fetched_pages.append((final_url, page))
                for candidate in _relevant_links(page, final_url):
                    if candidate not in visited_urls and candidate not in pending_urls:
                        pending_urls.append(candidate)

        summaries = []
        for source_url, page in fetched_pages:
            details = []
            if page["title"]:
                details.append(f"Page title: {page['title']}")
            if page["description"]:
                details.append(f"Meta description: {page['description']}")
            if page["headings"]:
                details.append(f"Key headings: {page['headings'][:400]}")
            if page["body"]:
                details.append(f"Page content excerpt: {page['body'][:_MAX_PAGE_CHARS]}")
            summaries.append(" | ".join(details))

        summary = "\n".join(summaries).strip()
        if not summary:
            return None
        return {
            "website_summary": summary[:_MAX_CHARS],
            "website_sources": list(dict.fromkeys(source for source, _ in fetched_pages)),
        }

    except Exception as exc:
        logger.info("Website fetch for %s failed (%s); skipping.", normalized, exc.__class__.__name__)
        return None


def fetch_website_summary(url: str | None) -> str | None:
    research = fetch_website_research(url)
    return research["website_summary"] if research else None


def fetch_linkedin_hint(url: str | None) -> str | None:
    """
    LinkedIn requires a logged-in session to view profile/company pages and
    actively blocks automated/unauthenticated scraping (both technically,
    via bot detection, and in its Terms of Service). An unauthenticated GET
    request to a linkedin.com URL will reliably return a login wall, not the
    real profile or company content - so this deliberately does NOT attempt
    to fetch or scrape the page.

    Instead, this derives a small, honest naming hint from the URL slug
    itself (e.g. ".../company/acme-robotics" -> "acme robotics"), clearly
    labeled as URL-derived only, so the AI can use it as a light naming cue
    without treating it as verified profile data.
    """
    if not url or not url.strip():
        return None

    match = re.search(r"linkedin\.com/(in|company)/([^/?#]+)", url, re.IGNORECASE)
    if not match:
        return None

    kind, slug = match.group(1).lower(), match.group(2)
    readable = re.sub(r"[-_]+", " ", slug).strip()
    if not readable:
        return None

    entity = "person" if kind == "in" else "company"
    return (
        f"LinkedIn URL-derived hint only (page content not accessible without login): "
        f"this is a {entity} profile, slug suggests the name '{readable}'."
    )


def build_research(lead) -> dict:
    """
    Runs both research steps for a lead and returns only the non-empty
    results, keyed for direct inclusion in the AI payload under "research".
    Never raises - both underlying fetchers are already fully guarded.
    """
    research = {}

    website_research = fetch_website_research(getattr(lead, "website", None))
    if website_research:
        research.update(website_research)

    linkedin_hint = fetch_linkedin_hint(getattr(lead, "linkedin", None))
    if linkedin_hint:
        research["linkedin_hint"] = linkedin_hint

    return research
