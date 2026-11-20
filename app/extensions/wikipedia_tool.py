import urllib.request
import urllib.parse
import json
from typing import Dict, Any, Optional

class WikipediaTool:
    """Free Wikipedia REST API client for summary and search."""

    HEADERS = {
        "User-Agent": "SuperOllama/1.0 (offline-desktop-client@local.dev)"
    }

    @classmethod
    def search_and_summary(cls, query: str) -> Dict[str, Any]:
        """Search Wikipedia and retrieve the best matching article's summary."""
        try:
            # 1. Search for title
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded_query}&limit=3&namespace=0&format=json"
            req = urllib.request.Request(search_url, headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            # Format: [query, [titles], [descriptions], [urls]]
            if not data or len(data) < 4 or not data[1]:
                return {"success": False, "error": f"No Wikipedia articles found for '{query}'"}
            
            best_title = data[1][0]
            canonical_url = data[3][0]

            # 2. Get detailed summary via REST API
            encoded_title = urllib.parse.quote(best_title.replace(" ", "_"))
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
            req2 = urllib.request.Request(summary_url, headers=cls.HEADERS)
            with urllib.request.urlopen(req2, timeout=6) as resp2:
                summary_data = json.loads(resp2.read().decode("utf-8"))
            
            extract = summary_data.get("extract", "")
            description = summary_data.get("description", "")
            
            return {
                "success": True,
                "title": best_title,
                "description": description,
                "extract": extract,
                "url": canonical_url,
                "source": "Wikipedia"
            }
        except Exception as e:
            return {"success": False, "error": f"Wikipedia query error: {str(e)}"}
