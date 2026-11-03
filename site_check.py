"""Checks whether a brand's website is easy for AI assistants to read and understand.

No AI is used here: it's plain code reading the homepage, robots.txt and llms.txt,
so these checks are free, fast, and give the same answer every time.
"""

import json
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; AI-Visibility-Agent/1.0)"
# Long homepages get cut to this many characters before they're sent to the AI for the fix list.
MAX_TEXT_CHARS = 12_000

# The crawlers that feed the big AI assistants, and who runs them.
AI_CRAWLERS = {
    "GPTBot": "OpenAI (ChatGPT training)",
    "OAI-SearchBot": "OpenAI (ChatGPT search)",
    "ClaudeBot": "Anthropic (Claude)",
    "PerplexityBot": "Perplexity",
    "Google-Extended": "Google (Gemini)",
}


def normalize_url(raw):
    """Adds https:// if it's missing and checks the result looks like a web address."""
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc or "." not in parsed.netloc:
        return None
    return raw


def fetch(url):
    """Downloads a page, trying twice. Returns the response, or None if the site couldn't be reached."""
    response = None
    for _ in range(2):
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        except requests.RequestException:
            continue
        if not blocked(response):
            break
    return response


def blocked(response):
    """True when a site refused our visit (bot protection, rate limits, or a server error), so we can't tell either way."""
    return response is None or response.status_code in (401, 403, 429) or response.status_code >= 500


def json_ld_types(soup):
    """Lists the schema.org types (Organization, FAQPage, Product...) found in the page's JSON-LD blocks."""
    types = []

    def collect(item):
        if isinstance(item, list):
            for entry in item:
                collect(entry)
        elif isinstance(item, dict):
            kind = item.get("@type")
            for name in kind if isinstance(kind, list) else [kind]:
                if isinstance(name, str) and name not in types:
                    types.append(name)
            # Some sites bundle several items into one "@graph" list.
            collect(item.get("@graph", []))
            collect(item.get("mainEntity", []))

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            collect(json.loads(tag.string or ""))
        except json.JSONDecodeError:
            continue
    return types


def question_headings(soup):
    """Finds headings written as questions, like 'How much does it cost?', which AI assistants love to quote."""
    return [
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h2", "h3", "h4", "summary", "dt", "button"])
        if h.get_text(strip=True).endswith("?")
    ]


def check_robots(homepage):
    """Reads robots.txt and works out which AI crawlers may visit the homepage."""
    robots_url = urljoin(homepage, "/robots.txt")
    response = fetch(robots_url)
    if blocked(response):
        return {"found": None, "allowed": None}
    if response.status_code >= 400 or "<html" in response.text[:500].lower():
        # No robots.txt means every crawler is welcome.
        return {"found": False, "allowed": {bot: True for bot in AI_CRAWLERS}}
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return {
        "found": True,
        "allowed": {bot: parser.can_fetch(bot, homepage) for bot in AI_CRAWLERS},
    }


def check_llms_txt(homepage):
    """Looks for an llms.txt file: a plain-text summary of the site written for AI assistants.

    Returns True or False, or None if the site blocked the check.
    """
    response = fetch(urljoin(homepage, "/llms.txt"))
    if blocked(response):
        return None
    if response.status_code != 200:
        return False
    # Some sites answer every address with their homepage, so make sure this is really a text file.
    return "<html" not in response.text[:500].lower() and len(response.text.strip()) > 50


def check_site(url):
    """Runs every AI-readiness check on a homepage.

    Returns a dict with the checks and a short text extract of the page (for the AI to write fixes from),
    or None if the homepage couldn't be loaded.
    """
    response = fetch(url)
    if response is None or response.status_code >= 400:
        return None
    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"})
    description = meta.get("content", "").strip() if meta else ""
    schema_types = json_ld_types(soup)
    questions = question_headings(soup)
    robots = check_robots(response.url)
    has_llms_txt = check_llms_txt(response.url)

    # Text extract for the fix list. Remove code and other invisible parts first.
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    headings = [
        f"{h.name.upper()}: {h.get_text(' ', strip=True)}"
        for h in soup.find_all(["h1", "h2", "h3"])
        if h.get_text(strip=True)
    ]
    body = " ".join(soup.get_text(" ", strip=True).split())[:MAX_TEXT_CHARS]
    extract = "\n\n".join([
        f"TITLE: {title or '(none)'}",
        f"META DESCRIPTION: {description or '(none)'}",
        "HEADINGS:\n" + ("\n".join(headings[:40]) or "(none)"),
        f"VISIBLE TEXT:\n{body}",
    ])

    blocked_bots = [bot for bot, allowed in (robots["allowed"] or {}).items() if not allowed]
    has_faq = "FAQPage" in schema_types or len(questions) >= 3
    has_org = any(t in schema_types for t in ("Organization", "Corporation", "LocalBusiness", "OnlineStore"))
    checks = [
        {
            "name": "AI crawlers allowed",
            # None means the site refused our visit, so we can't say either way.
            "passed": None if robots["allowed"] is None else not blocked_bots,
            "detail": (
                "Couldn't check: the site blocked our visit to its robots.txt."
                if robots["allowed"] is None
                else "robots.txt lets all the major AI crawlers in."
                if not blocked_bots
                else "robots.txt blocks " + ", ".join(f"{b} ({AI_CRAWLERS[b]})" for b in blocked_bots) + "."
            ),
        },
        {
            "name": "Structured data (JSON-LD)",
            "passed": bool(schema_types),
            "detail": (
                "Found schema types: " + ", ".join(schema_types[:8]) + "."
                if schema_types
                else "No JSON-LD in the homepage's HTML. Most AI crawlers don't run JavaScript, "
                "so schema added by scripts is invisible to them, and they're left guessing what the business is."
            ),
        },
        {
            "name": "Organization schema",
            "passed": has_org,
            "detail": (
                "Found. It tells AI the brand's official name, logo, and social profiles in a format it can trust."
                if has_org
                else "Missing. This is how a site tells AI its official name, logo, and social profiles in a format it can trust."
            ),
        },
        {
            "name": "FAQ content",
            "passed": has_faq,
            "detail": (
                f"Found FAQPage schema and/or {len(questions)} question-style headings."
                if has_faq
                else "Few or no question-and-answer sections. AI assistants are answering questions, so give them answers to quote."
            ),
        },
        {
            "name": "llms.txt file",
            "passed": has_llms_txt,
            "detail": (
                "Found an llms.txt summary for AI assistants."
                if has_llms_txt
                else "Couldn't check: the site blocked our visit to its llms.txt address."
                if has_llms_txt is None
                else "No llms.txt yet. It's a newer, optional standard, but a cheap way to hand AI a clean summary."
            ),
        },
        {
            "name": "Title and meta description",
            "passed": bool(title and description),
            "detail": (
                "Both present. This one-line summary is often reused when AI describes a brand."
                if title and description
                else "Missing the page title or meta description, the one-line summary AI often reuses to describe a brand."
            ),
        },
    ]
    return {
        "url": response.url,
        "checks": checks,
        "score": sum(c["passed"] is True for c in checks),
        "schema_types": schema_types,
        "robots_found": robots["found"],
        "blocked_crawlers": blocked_bots,
        "extract": extract,
    }
