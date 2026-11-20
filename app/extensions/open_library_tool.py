import urllib.request
import urllib.parse
import json
from typing import Dict, Any, List

class OpenLibraryTool:
    """Free Open Library & Gutenberg book catalog search tool."""

    HEADERS = {
        "User-Agent": "SuperOllama/1.0 (books@local)"
    }

    @classmethod
    def search_books(cls, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search Open Library for book titles, authors, first publish year, and ratings."""
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://openlibrary.org/search.json?q={encoded_query}&limit={limit}"
            req = urllib.request.Request(url, headers=cls.HEADERS)
            
            with urllib.request.urlopen(req, timeout=7) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            docs = data.get("docs", [])
            formatted = []
            for doc in docs[:limit]:
                authors = doc.get("author_name", ["Unknown Author"])
                first_year = doc.get("first_publish_year", "N/A")
                title = doc.get("title", "")
                cover_id = doc.get("cover_i")
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ""
                key = doc.get("key", "")
                
                formatted.append({
                    "title": title,
                    "authors": ", ".join(authors) if isinstance(authors, list) else str(authors),
                    "first_publish_year": first_year,
                    "cover_url": cover_url,
                    "url": f"https://openlibrary.org{key}" if key else ""
                })

            return {
                "success": True,
                "query": query,
                "total_found": data.get("numFound", 0),
                "books": formatted,
                "source": "Open Library"
            }
        except Exception as e:
            return {"success": False, "error": f"Open Library error: {str(e)}"}
