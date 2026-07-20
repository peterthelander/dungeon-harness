import json
import logging
import urllib.parse
import threading
import time

from flask import jsonify
from google.genai import types


logger = logging.getLogger(__name__)

SEARCH_PROMPT = """
Use Google Search to find freely and legally published tabletop fantasy roleplaying
adventure modules available as direct PDF downloads. Favor PDFs hosted by their
authors, publishers, community project sites, or established open-RPG repositories.
Do not include unauthorized scans of commercial books, storefront previews, samples,
rulebooks, character sheets, templates, Scribd, document mirrors, or search-result
pages. Return up to 15 candidates so the application can filter them. Every URL must
point directly to a PDF, not to a landing page. Provide concise factual descriptions;
Return only valid JSON with an adventures array containing title, url, source, description, and details strings.
do not invent level ranges or game systems when the source does not state them.
""".strip()


BLOCKED_SEARCH_DOMAINS = {
    "anyflip.com",
    "docslib.org",
    "manuals.plus",
    "pdfcoffee.com",
    "pdfroom.com",
    "scribd.com",
}



def _parse_search_payload(raw_text):
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text or "{}")
def _clean_text(value, maximum):
    return " ".join(str(value or "").split())[:maximum]


def filter_adventure_results(items, limit=10):
    results = []
    seen_urls = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        raw_url = str(item.get("url") or "").strip()
        parsed = urllib.parse.urlparse(raw_url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not hostname:
            continue
        if any(hostname == domain or hostname.endswith(f".{domain}") for domain in BLOCKED_SEARCH_DOMAINS):
            continue
        if not parsed.path.lower().endswith(".pdf"):
            continue
        normalized_url = parsed.geturl()
        if normalized_url in seen_urls:
            continue
        title = _clean_text(item.get("title"), 120)
        description = _clean_text(item.get("description"), 260)
        if not title or not description:
            continue
        seen_urls.add(normalized_url)
        results.append({
            "title": title,
            "url": normalized_url,
            "source": _clean_text(item.get("source") or hostname, 80),
            "description": description,
            "details": _clean_text(item.get("details") or "Free web PDF · Not yet tested", 100),
        })
        if len(results) == limit:
            break
    return results

SEARCH_CACHE_SECONDS = 15 * 60
_search_cache = {"expires_at": 0.0, "results": None}
_search_lock = threading.Lock()


def discover_adventures():
    from app.engine import model_client

    response = model_client.client.models.generate_content(
        model="gemini-2.5-flash",
        contents=SEARCH_PROMPT,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    payload = _parse_search_payload(response.text)
    search_html = ""
    if response.candidates:
        metadata = getattr(response.candidates[0], "grounding_metadata", None)
        entry_point = getattr(metadata, "search_entry_point", None)
        search_html = getattr(entry_point, "rendered_content", "") or ""
    return {
        "adventures": filter_adventure_results(payload.get("adventures")),
        "google_search_html": search_html,
    }


def get_cached_adventures():
    now = time.monotonic()
    if _search_cache["results"] is not None and now < _search_cache["expires_at"]:
        return _search_cache["results"]
    with _search_lock:
        now = time.monotonic()
        if _search_cache["results"] is not None and now < _search_cache["expires_at"]:
            return _search_cache["results"]
        results = discover_adventures()
        _search_cache["results"] = results
        _search_cache["expires_at"] = now + SEARCH_CACHE_SECONDS
        return results

def register_adventure_search_route(app):
    @app.route("/discover-adventures", methods=["GET"])
    def discover_adventures_route():
        try:
            payload = get_cached_adventures()
            if not payload["adventures"]:
                return jsonify({"adventures": [], "error": "No suitable adventure PDFs were found."}), 503
            return jsonify(payload)
        except Exception:
            logger.exception("adventure_search.failed")
            return jsonify({"adventures": [], "error": "Adventure discovery is temporarily unavailable."}), 503
