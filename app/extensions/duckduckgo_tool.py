from typing import Dict, Any, List

class DuckDuckGoTool:
    """DuckDuckGo Search & Instant Answers tool using ddgs."""

    @classmethod
    def search(cls, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search DuckDuckGo for web text results."""
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            
            formatted = []
            for item in results:
                formatted.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("body", ""),
                    "url": item.get("href", "")
                })

            return {
                "success": True,
                "query": query,
                "count": len(formatted),
                "results": formatted,
                "source": "DuckDuckGo"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"DuckDuckGo search error: {str(e)}"
            }
