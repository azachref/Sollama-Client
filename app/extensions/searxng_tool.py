import urllib.request
import urllib.parse
import json
from typing import Dict, Any, List

class SearXNGTool:
    """SearXNG meta-search engine client."""

    @classmethod
    def search(cls, base_url: str, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Query a local or remote SearXNG instance."""
        clean_base = base_url.rstrip("/")
        encoded_query = urllib.parse.quote(query)
        search_url = f"{clean_base}/search?q={encoded_query}&format=json&language=auto"
        
        headers = {
            "User-Agent": "SuperOllama/1.0 (client@local)",
            "Accept": "application/json"
        }
        
        try:
            req = urllib.request.Request(search_url, headers=headers)
            with urllib.request.urlopen(req, timeout=7) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            raw_results = data.get("results", [])
            formatted = []
            for item in raw_results[:max_results]:
                formatted.append({
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                    "url": item.get("url", ""),
                    "engine": item.get("engine", "searxng")
                })
            
            return {
                "success": True,
                "query": query,
                "count": len(formatted),
                "results": formatted,
                "source": "SearXNG"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"SearXNG connection error at {base_url}: {str(e)}"
            }
