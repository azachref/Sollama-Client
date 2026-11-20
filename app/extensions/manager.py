"""
Extension Manager — Smart intent routing & tool execution for SuperOllama.

Detects user intent via pattern matching and executes the appropriate
extension (Open-Meteo weather, Wikipedia, ZIM offline, SearXNG, DuckDuckGo,
Open Library).  Results are formatted into prompt context blocks that the
LLM can reference in its answer.
"""

import re
import traceback
from typing import Dict, Any, List, Optional, Tuple
from app.database import get_setting
from app.extensions.wikipedia_tool import WikipediaTool
from app.extensions.open_meteo_tool import OpenMeteoTool
from app.extensions.searxng_tool import SearXNGTool
from app.extensions.duckduckgo_tool import DuckDuckGoTool
from app.extensions.open_library_tool import OpenLibraryTool
from app.extensions.zim_tool import ZimTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOCATION_NOISE = re.compile(
    r'(?i)\b(?:right\s+now|today|tomorrow|now|currently|please|this\s+week'
    r'|this\s+weekend|outside|like)\b'
)

def _clean(query: str, prefix_words: List[str] = None, suffix_words: List[str] = None) -> str:
    """Strip surrounding punctuation and optional filler words."""
    q = query.strip()
    q = re.sub(r'^[^\w]+|[^\w]+$', '', q).strip()
    for sw in (prefix_words or []):
        q = re.sub(rf'(?i)^{re.escape(sw)}\s+', '', q).strip()
    for sw in (suffix_words or []):
        q = re.sub(rf'(?i)\s+{re.escape(sw)}$', '', q).strip()
    return q


class ExtensionManager:
    """Manages tool execution, configuration, and intelligent intent routing."""

    # ------------------------------------------------------------------
    # Intent Detection
    # ------------------------------------------------------------------
    @classmethod
    def detect_intent(cls, user_message: str) -> Optional[Tuple[str, str]]:
        """
        Analyze user message to determine if an active extension should run.
        Returns (tool_name, extracted_query) or None.
        
        Tool names: "open_meteo", "open_library", "encyclopedia", "zim",
                    "web_search"
        """
        msg = user_message.strip()
        lower = msg.lower()

        # ── 0. Explicit ZIM / offline search ──────────────────────────
        zim_m = re.search(
            r'(?i)\b(?:search\s+zim(?:\s+for)?|zim\s+search\s*:?'
            r'|offline\s+(?:wikipedia|search|encyclopedia)\s*(?:for)?'
            r'|check\s+offline\s+(?:wikipedia|zim)\s+(?:for)?)\s*(.*)', msg)
        if zim_m:
            q = _clean(zim_m.group(1))
            if q:
                return ("zim", q)

        # ── 1. Weather ────────────────────────────────────────────────
        weather_kws = [
            "weather", "temperature", "forecast", "climate",
            "how hot", "how cold", "is it raining", "is it snowing",
            "rain forecast", "snow forecast"
        ]
        if any(w in lower for w in weather_kws):
            loc = cls._extract_weather_location(msg)
            return ("open_meteo", loc)

        # ── 2. Books / Literature ─────────────────────────────────────
        book_patterns = [
            r'\b(?:books?\s+by|novels?\s+by|author\s+of|written\s+by)\s+([a-zA-Z0-9\s,.\'-]{2,50})',
            r'\b(?:find\s+books?|search\s+books?|lookup\s+books?)\s+(?:by|for|about)?\s*([a-zA-Z0-9\s,.\'-]{2,50})',
            r'\bwhat\s+books?\s+did\s+([a-zA-Z\s]{2,40})\s+write\b',
            r'\b(?:open\s+library|gutendex)\s*(?:search\s*:?|for)?\s*([a-zA-Z0-9\s,.\'-]{2,50})',
        ]
        for bp in book_patterns:
            bm = re.search(bp, msg, re.IGNORECASE)
            if bm:
                q = _clean(bm.group(1))
                if q:
                    return ("open_library", q)

        # ── 3. Wikipedia / Encyclopedia ───────────────────────────────
        # 3a. Explicit "wikipedia" in message
        if "wikipedia" in lower:
            clean = re.sub(
                r'(?i)\b(?:can\s+you\s+)?(?:please\s+)?'
                r'(?:use\s+wikipedia\s+(?:to\s+find(?:\s+info\s+on)?|to\s+look\s*up|for)?'
                r'|search\s+wikipedia\s+(?:for)?'
                r'|check\s+wikipedia\s+(?:for)?'
                r'|look\s+up(?:\s+on)?\s+wikipedia'
                r'|on\s+wikipedia'
                r'|wikipedia\s*:?)\b', '', msg)
            clean = re.sub(r'(?i)\b(?:look\s+up|search|find|check)\b', '', clean)
            clean = _clean(clean, prefix_words=[
                "info on", "information on", "information about",
                "for", "about", "article on", "article about"
            ])
            if clean:
                return ("encyclopedia", clean)

        # 3b. General knowledge questions (who is, what is, tell me about…)
        coding_kws = [
            "code", "python", "function", "javascript", "typescript",
            "class ", "def ", "import ", "write a", "create a", "how to",
            "implement", "build a", "make a", "program"
        ]
        if not any(kw in lower for kw in coding_kws):
            knowledge_patterns = [
                r'(?i)\b(?:who\s+is|who\s+was)\s+([a-zA-Z0-9\s,.\'-]{2,60})',
                r'(?i)\b(?:what\s+is|what\s+was|what\s+are)\s+([a-zA-Z0-9\s,.\'-]{2,60})',
                r'(?i)\b(?:tell\s+me\s+about|explain|describe|history\s+of|summary\s+of)\s+([a-zA-Z0-9\s,.\'-]{2,60})',
                r'(?i)\b(?:biography\s+of|who\s+created|who\s+invented)\s+([a-zA-Z0-9\s,.\'-]{2,60})',
                r'(?i)\b(?:define)\s+([a-zA-Z0-9\s,.\'-]{2,40})',
            ]
            skip_answers = {
                "your name", "the time", "the weather", "a joke",
                "love", "life", "up", "going on", "that", "this",
                "it", "you", "me", "us"
            }
            for wp in knowledge_patterns:
                wm = re.search(wp, msg)
                if wm:
                    cand = _clean(wm.group(1), prefix_words=["the", "a", "an"])
                    if cand and cand.lower() not in skip_answers and len(cand) > 1:
                        return ("encyclopedia", cand)

        # ── 4. Web Search ────────────────────────────────────────────
        web_patterns = [
            # Explicit search instructions
            r'(?i)\b(?:use\s+(?:your\s+)?(?:web\s+)?search\s+tool\s*(?:for|to\s+search\s+for|to\s+find|to)?|use\s+web\s+search\s+to\s+find)\s+(.+)',
            r'(?i)\b(?:search\s+(?:the\s+)?web\s+(?:for)?|search\s+online\s+(?:for)?|look\s+up\s+online\s+(?:for)?|browse\s+the\s+web\s+(?:for)?)\s+(.+)',
            r'(?i)\b(?:web\s*search|search\s+(?:the\s+)?web|search\s+online|search\s+(?:the\s+)?internet)\s*[:\-]?\s*(.+)',
            r'(?i)\b(?:search\s+duckduckgo|search\s+ddgs|search\s+searxng|search\s+searx)\s+(?:for\s+)?(.+)',
            r'(?i)\b(?:google|duckduckgo|searxng|ddgs)\s*[:\-]\s*(.+)',
            r'(?i)\b(?:find\s+online\s+(?:information\s+)?(?:about|on|for)?)\s+(.+)',
            # Generic "search for …"
            r'(?i)\b(?:search\s+for)\s+([a-zA-Z0-9\s,.\'-]{3,80})',
            # News / current events
            r'(?i)\b(?:latest\s+news|breaking\s+news|current\s+events|recent\s+news)\s*(?:about|on|for)?\s*(.*)',
            r'(?i)\b(?:latest\s+price\s+of|current\s+price\s+of|stock\s+price\s+of)\s+(.+)',
        ]
        for wp in web_patterns:
            sm = re.search(wp, msg)
            if sm:
                raw_q = sm.group(1).strip() if sm.group(1).strip() else "latest news"
                q = _clean(raw_q, prefix_words=["for", "about", "on", "information about", "info on"])
                if q:
                    return ("web_search", q)

        return None

    # ------------------------------------------------------------------
    @classmethod
    def _extract_weather_location(cls, msg: str) -> str:
        """Best-effort extraction of a city/location from a weather query."""
        # A: Explicit tool phrasing
        tool_m = re.search(
            r'(?i)\b(?:use\s+(?:the\s+)?weather\s+(?:tool|extension)\s*'
            r'(?:to\s+check|to\s+get|for|in)?)\s+(.+)', msg)
        if tool_m:
            raw = tool_m.group(1)
            raw = re.sub(r'(?i)\bthe\s+weather\s+(?:in|for|at)\b', '', raw)
            raw = re.sub(r'(?i)\bweather\s+(?:in|for|at)\b', '', raw)
            loc = _LOCATION_NOISE.sub('', raw).strip()
            loc = re.sub(r'^[^\w]+|[^\w]+$', '', loc).strip()
            if loc:
                return loc

        # B: "weather like in Tokyo"
        like_m = re.search(r'(?i)\bweather\s+like\s+in\s+([a-zA-Z\s,.-]+)', msg)
        if like_m:
            loc = _LOCATION_NOISE.sub('', like_m.group(1)).strip()
            loc = re.sub(r'^[^\w]+|[^\w]+$', '', loc).strip()
            if loc:
                return loc

        # C: Last preposition phrase → "in Paris", "for London", "at Tokyo"
        # We want the LAST occurrence to avoid matching "is" in "what is"
        prep_matches = list(re.finditer(
            r'\b(?:in|for|at|around|near)\s+([a-zA-Z][a-zA-Z\s,.-]*)', msg, re.IGNORECASE))
        if prep_matches:
            loc = prep_matches[-1].group(1).strip()
            loc = _LOCATION_NOISE.sub('', loc).strip()
            loc = re.sub(r'^[^\w]+|[^\w]+$', '', loc).strip()
            if loc and len(loc) >= 2:
                return loc

        # D: Bare "weather Tokyo", "forecast Berlin"
        city_m = re.search(
            r'(?i)\b(?:weather|forecast|temperature)\s*[:\-]?\s*([a-zA-Z][a-zA-Z\s]{1,29})', msg)
        if city_m:
            loc = _clean(city_m.group(1), prefix_words=["of", "for", "in", "at", "the", "like"])
            loc = _LOCATION_NOISE.sub('', loc).strip()
            stops = {"report", "channel", "app", "tool", "station", "is"}
            if loc and loc.lower() not in stops:
                return loc

        return "London"  # sensible fallback

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------
    @classmethod
    def execute_tool(cls, tool_name: str, query: str) -> Optional[Dict[str, Any]]:
        """Execute the requested tool if enabled in settings.  Returns a
        result dict with keys: tool, icon, summary, data — or None."""
        auto_route = get_setting("ext_auto_route", True)
        if not auto_route:
            return None

        try:
            # ── Weather ───────────────────────────────────────────────
            if tool_name == "open_meteo":
                if get_setting("ext_open_meteo_enabled", True):
                    res = OpenMeteoTool.get_weather(query)
                    if res.get("success"):
                        return {
                            "tool": "Open-Meteo Weather",
                            "icon": "🌤️",
                            "summary": f"Weather in {res['location']}: {res['temperature']}, {res['condition']}",
                            "data": res
                        }

            # ── Open Library ──────────────────────────────────────────
            elif tool_name == "open_library":
                if get_setting("ext_open_library_enabled", True):
                    res = OpenLibraryTool.search_books(query)
                    if res.get("success") and res.get("books"):
                        first = res["books"][0]["title"]
                        return {
                            "tool": "Open Library",
                            "icon": "📚",
                            "summary": f"Found {res['total_found']} books for '{query}' (Top: {first})",
                            "data": res
                        }

            # ── Explicit ZIM offline ──────────────────────────────────
            elif tool_name == "zim":
                if get_setting("ext_zim_enabled", True):
                    zim_res = ZimTool.search_offline(
                        query, api_url=get_setting("ext_zim_api_url", ""))
                    if zim_res.get("success"):
                        return {
                            "tool": "Offline ZIM Knowledge",
                            "icon": "💾",
                            "summary": f"Offline entry: {zim_res.get('title', query)}",
                            "data": zim_res
                        }

            # ── Encyclopedia (ZIM first → Wikipedia fallback) ─────────
            elif tool_name == "encyclopedia":
                # Try offline ZIM first
                if get_setting("ext_zim_enabled", True):
                    zim_res = ZimTool.search_offline(
                        query, api_url=get_setting("ext_zim_api_url", ""))
                    if zim_res.get("success"):
                        return {
                            "tool": "Offline ZIM Knowledge",
                            "icon": "💾",
                            "summary": f"Offline entry: {zim_res.get('title', query)}",
                            "data": zim_res
                        }

                # Fallback to online Wikipedia
                if get_setting("ext_wikipedia_enabled", True):
                    wiki_res = WikipediaTool.search_and_summary(query)
                    if wiki_res.get("success"):
                        return {
                            "tool": "Wikipedia",
                            "icon": "🌐",
                            "summary": f"Wikipedia: {wiki_res['title']}",
                            "data": wiki_res
                        }

            # ── Web Search (SearXNG → DDGS fallback) ──────────────────
            elif tool_name == "web_search":
                # Try SearXNG if enabled
                if get_setting("ext_searxng_enabled", True):
                    searxng_url = get_setting("ext_searxng_url", "http://192.168.1.101:8080")
                    # Normalise: strip trailing /search path to prevent doubling
                    searxng_url = re.sub(r'/search\s*$', '', searxng_url.rstrip('/'))
                    try:
                        searx_res = SearXNGTool.search(searxng_url, query)
                        if searx_res.get("success") and searx_res.get("results"):
                            return {
                                "tool": "SearXNG Search",
                                "icon": "🔍",
                                "summary": f"SearXNG results for '{query}'",
                                "data": searx_res
                            }
                    except Exception:
                        pass  # fall through to DDGS

                # Fallback to DuckDuckGo if enabled
                if get_setting("ext_ddgs_enabled", True):
                    ddg_res = DuckDuckGoTool.search(query)
                    if ddg_res.get("success") and ddg_res.get("results"):
                        return {
                            "tool": "DuckDuckGo",
                            "icon": "🦆",
                            "summary": f"Web results for '{query}'",
                            "data": ddg_res
                        }

        except Exception as e:
            print(f"[ExtensionManager] execute_tool error ({tool_name}, {query}): {e}")
            traceback.print_exc()

        return None

    # ------------------------------------------------------------------
    # Prompt Formatting
    # ------------------------------------------------------------------
    @classmethod
    def format_tool_context(cls, tool_result: Dict[str, Any]) -> str:
        """Format tool result into a clear prompt context block that the LLM
        is instructed to use as the primary source for its answer."""
        tool_name = tool_result.get("tool", "")
        data = tool_result.get("data", {})

        preamble = (
            "\n[TOOL DATA — USE THIS AS YOUR PRIMARY SOURCE.  "
            "Base your answer on the data below.  "
            "Present it clearly and conversationally.  "
            "Cite the source tool.]\n"
        )

        if "Open-Meteo" in tool_name:
            fc_lines = [
                f"  • {f['date']}: {f['condition']}, High {f['max_temp']}, Low {f['min_temp']}, Precipitation {f.get('precip_prob', 'N/A')}"
                for f in data.get("forecast", [])
            ]
            fc_str = "\n".join(fc_lines)
            body = (
                f"Source: {tool_name}\n"
                f"Location: {data.get('location')}\n"
                f"Condition: {data.get('condition')}\n"
                f"Current Temp: {data.get('temperature')} (Feels like {data.get('feels_like')})\n"
                f"Humidity: {data.get('humidity')}, Wind: {data.get('wind_speed')}\n"
                f"Upcoming Forecast:\n{fc_str}\n"
            )
            return preamble + body + "[END TOOL DATA]\n"

        elif "Wikipedia" in tool_name:
            body = (
                f"Source: Wikipedia\n"
                f"Title: {data.get('title')}\n"
                f"Description: {data.get('description', '')}\n"
                f"Content:\n{data.get('extract')}\n"
                f"Reference URL: {data.get('url')}\n"
            )
            return preamble + body + "[END TOOL DATA]\n"

        elif "ZIM" in tool_name:
            body = (
                f"Source: {data.get('source', 'ZIM Offline')}\n"
                f"Title: {data.get('title')}\n"
                f"Content:\n{data.get('snippet')}\n"
            )
            return preamble + body + "[END TOOL DATA]\n"

        elif "Open Library" in tool_name:
            books = data.get("books", [])
            lines = [
                f"  • \"{b['title']}\" by {b['authors']} (First published: {b['first_publish_year']})"
                for b in books
            ]
            body = (
                f"Source: Open Library / Gutendex\n"
                f"Search query: {data.get('query')}\n"
                f"Total found: {data.get('total_found', len(books))}\n"
                f"Top results:\n" + "\n".join(lines) + "\n"
            )
            return preamble + body + "[END TOOL DATA]\n"

        elif "SearXNG" in tool_name or "DuckDuckGo" in tool_name:
            items = data.get("results", [])
            lines = []
            for item in items:
                title = item.get("title", "")
                snippet = item.get("content") or item.get("snippet", "")
                url = item.get("url", "")
                lines.append(f"  • **{title}**: {snippet}  ({url})")
            body = (
                f"Source: {tool_name}\n"
                f"Search query: {data.get('query')}\n"
                f"Results:\n" + "\n".join(lines) + "\n"
            )
            return preamble + body + "[END TOOL DATA]\n"

        return ""

    # ------------------------------------------------------------------
    @classmethod
    def get_enabled_tools_summary(cls) -> str:
        """Return a compact system-prompt snippet listing which tools are
        currently enabled so the LLM knows its capabilities."""
        lines = ["You have access to these live tools (auto-routed):"]
        if get_setting("ext_open_meteo_enabled", True):
            lines.append("  • Open-Meteo (real-time weather & forecasts)")
        if get_setting("ext_wikipedia_enabled", True):
            lines.append("  • Wikipedia (online encyclopedia)")
        if get_setting("ext_zim_enabled", True):
            lines.append("  • ZIM offline encyclopedia")
        if get_setting("ext_searxng_enabled", True):
            lines.append("  • SearXNG (web search)")
        if get_setting("ext_ddgs_enabled", True):
            lines.append("  • DuckDuckGo (web search)")
        if get_setting("ext_open_library_enabled", True):
            lines.append("  • Open Library / Gutendex (book search)")
        lines.append(
            "When these tools are invoked, their results are injected below "
            "as [TOOL DATA].  Use that data as your primary source and present "
            "it clearly."
        )
        return "\n".join(lines)
