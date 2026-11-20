import os
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from app.config import ZIM_DIR

# Curated catalog of tested & verified ZIM files (with live tested mirrors)
CURATED_ZIM_CATALOG = [
    {
        "id": "wiki-en-simple-mini",
        "name": "Wikipedia Simple English (Mini)",
        "description": "Essential knowledge in Simple English without images. Very compact & fast.",
        "size_str": "505 MB",
        "size_bytes": 530482005,
        "category": "Encyclopedia",
        "url": "https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en-simple_all_mini_2026-09.zim",
        "filename": "wikipedia_en-simple_all_mini_2026-09.zim",
        "recommended": True,
        "is_huge": False
    },
    {
        "id": "wiki-en-100",
        "name": "Wikipedia Top 100 Articles",
        "description": "Top 100 most read Wikipedia articles. Extremely fast to download.",
        "size_str": "318 MB",
        "size_bytes": 333447168,
        "category": "Encyclopedia",
        "url": "https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en_100_2026-08.zim",
        "filename": "wikipedia_en_100_2026-08.zim",
        "recommended": True,
        "is_huge": False
    },
    {
        "id": "wiki-en-simple-nopic",
        "name": "Wikipedia Simple English (Complete, No Images)",
        "description": "All simple English articles with complete text definitions.",
        "size_str": "1.04 GB",
        "size_bytes": 1094936576,
        "category": "Encyclopedia",
        "url": "https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en-simple_all_nopic_2026-09.zim",
        "filename": "wikipedia_en-simple_all_nopic_2026-09.zim",
        "recommended": True,
        "is_huge": False
    },
    {
        "id": "wiki-en-astronomy",
        "name": "Astronomy by Wikipedia",
        "description": "Comprehensive astronomy, planets, space missions, and astrophysics.",
        "size_str": "1.68 GB",
        "size_bytes": 1765576704,
        "category": "Science",
        "url": "https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en_astronomy_maxi_2026-08.zim",
        "filename": "wikipedia_en_astronomy_maxi_2026-08.zim",
        "recommended": False,
        "is_huge": False
    },
    {
        "id": "wiki-en-football",
        "name": "Football / Soccer by Wikipedia",
        "description": "World cup, leagues, clubs, players, and match history.",
        "size_str": "2.69 GB",
        "size_bytes": 2826436608,
        "category": "Sports",
        "url": "https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en_football_nopic_2026-10.zim",
        "filename": "wikipedia_en_football_nopic_2026-10.zim",
        "recommended": False,
        "is_huge": False
    },
    {
        "id": "wiki-en-all-mini",
        "name": "Wikipedia English All (Mini / Introductions)",
        "description": "Every English Wikipedia article's summary and introduction.",
        "size_str": "13.7 GB",
        "size_bytes": 14386708480,
        "category": "Encyclopedia",
        "url": "https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en_all_mini_2026-09.zim",
        "filename": "wikipedia_en_all_mini_2026-09.zim",
        "recommended": False,
        "is_huge": True  # Warning: >10GB
    },
    {
        "id": "wiki-en-all-nopic",
        "name": "Wikipedia English Complete (Text Only)",
        "description": "Full text of ALL English Wikipedia articles. Very comprehensive but very large!",
        "size_str": "50.2 GB",
        "size_bytes": 52689371136,
        "category": "Encyclopedia",
        "url": "https://lb.download.kiwix.org/zim/wikipedia/wikipedia_en_all_nopic_2026-06.zim",
        "filename": "wikipedia_en_all_nopic_2026-06.zim",
        "recommended": False,
        "is_huge": True  # Warning: >10GB
    }
]

class ZimDownloadManager:
    """Manages background downloading of ZIM dumps with progress monitoring via httpx."""
    
    _lock = threading.Lock()
    _active_downloads: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_status(cls, item_id: str) -> Dict[str, Any]:
        with cls._lock:
            return cls._active_downloads.get(item_id, {"status": "idle", "percent": 0})

    @classmethod
    def get_all_statuses(cls) -> Dict[str, Dict[str, Any]]:
        with cls._lock:
            return dict(cls._active_downloads)

    @classmethod
    def start_download(cls, item_id: str, zim_dir: Path = ZIM_DIR) -> Dict[str, Any]:
        item = next((c for c in CURATED_ZIM_CATALOG if c["id"] == item_id), None)
        if not item:
            return {"success": False, "error": f"Item '{item_id}' not found in catalog."}

        target_file = zim_dir / item["filename"]
        if target_file.exists() and target_file.stat().st_size > 1000000:
            return {"success": False, "error": "File already downloaded."}

        with cls._lock:
            if item_id in cls._active_downloads and cls._active_downloads[item_id].get("status") == "downloading":
                return {"success": False, "error": "Download already in progress."}

            cls._active_downloads[item_id] = {
                "status": "downloading",
                "percent": 0.0,
                "downloaded_bytes": 0,
                "total_bytes": item["size_bytes"],
                "speed_mb": 0.0,
                "cancel_requested": False,
                "error": ""
            }

        thread = threading.Thread(
            target=cls._download_worker,
            args=(item_id, item["url"], target_file, item["size_bytes"]),
            daemon=True
        )
        thread.start()
        return {"success": True, "message": f"Started downloading {item['name']}"}

    @classmethod
    def cancel_download(cls, item_id: str):
        with cls._lock:
            if item_id in cls._active_downloads:
                cls._active_downloads[item_id]["cancel_requested"] = True

    @classmethod
    def _download_worker(cls, item_id: str, url: str, dest_path: Path, expected_size: int):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = dest_path.with_suffix(".part")
        try:
            # Use httpx with follow_redirects and generous timeout
            with httpx.Client(follow_redirects=True, timeout=30.0) as client:
                with client.stream("GET", url, headers={"User-Agent": "SuperOllama/1.0"}) as response:
                    if response.status_code != 200:
                        raise RuntimeError(f"Server returned HTTP {response.status_code}")

                    content_len_header = response.headers.get("content-length")
                    total_bytes = int(content_len_header) if content_len_header else expected_size
                    downloaded = 0
                    start_time = time.time()
                    last_update = time.time()

                    with open(temp_path, "wb") as f_out:
                        for chunk in response.iter_bytes(chunk_size=1024 * 512):
                            with cls._lock:
                                if cls._active_downloads.get(item_id, {}).get("cancel_requested"):
                                    cls._active_downloads[item_id]["status"] = "cancelled"
                                    break

                            if not chunk:
                                break
                            
                            f_out.write(chunk)
                            downloaded += len(chunk)

                            now = time.time()
                            if now - last_update >= 0.5:
                                elapsed = now - start_time
                                speed = (downloaded / (1024 * 1024)) / (elapsed if elapsed > 0 else 1)
                                percent = round((downloaded / total_bytes) * 100, 1) if total_bytes > 0 else 0
                                with cls._lock:
                                    cls._active_downloads[item_id].update({
                                        "status": "downloading",
                                        "percent": min(percent, 99.9),
                                        "downloaded_bytes": downloaded,
                                        "total_bytes": total_bytes,
                                        "speed_mb": round(speed, 2)
                                    })
                                last_update = now

            if temp_path.exists():
                with cls._lock:
                    if cls._active_downloads.get(item_id, {}).get("status") == "cancelled":
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
                        return

                temp_path.rename(dest_path)
                with cls._lock:
                    cls._active_downloads[item_id].update({
                        "status": "completed",
                        "percent": 100.0,
                        "downloaded_bytes": downloaded,
                        "speed_mb": 0.0
                    })

        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            with cls._lock:
                cls._active_downloads[item_id] = {
                    "status": "error",
                    "error": str(e),
                    "percent": 0.0,
                    "downloaded_bytes": 0,
                    "total_bytes": expected_size,
                    "speed_mb": 0.0
                }


class ZimTool:
    """Offline ZIM archive reader using libzim or Zim Pro / Kiwix HTTP API."""

    @classmethod
    def get_installed_zims(cls, zim_dir: Path = ZIM_DIR) -> List[Dict[str, Any]]:
        """List all .zim files currently available in the zim directory."""
        installed = []
        if not zim_dir.exists():
            return installed

        for f in zim_dir.glob("*.zim"):
            size_mb = round(f.stat().st_size / (1024 * 1024), 1)
            size_str = f"{size_mb} MB" if size_mb < 1024 else f"{round(size_mb / 1024, 2)} GB"
            
            matched = next((c for c in CURATED_ZIM_CATALOG if c["filename"] == f.name), None)
            installed.append({
                "filename": f.name,
                "path": str(f),
                "size_str": size_str,
                "title": matched["name"] if matched else f.stem.replace("_", " ").title(),
                "category": matched["category"] if matched else "Custom ZIM"
            })
        return installed

    @classmethod
    def search_offline(cls, query: str, zim_dir: Path = ZIM_DIR, api_url: str = "", active_filename: str = "") -> Dict[str, Any]:
        """Search offline ZIM archives using libzim or fallback to Zim Pro HTTP API."""
        installed = cls.get_installed_zims(zim_dir)
        if not installed:
            return {
                "success": False,
                "error": "No offline ZIM packages installed yet. Go to Settings -> ZIM Offline Downloads, and click 'Download' on Wikipedia Simple English (505 MB) to enable offline answers."
            }

        # If active_filename specified, prioritize it
        if not active_filename:
            from app.database import get_setting
            active_filename = get_setting("active_zim_filename", "")

        ordered_zims = []
        if active_filename:
            match = next((item for item in installed if item["filename"] == active_filename), None)
            if match:
                ordered_zims.append(match)
        for item in installed:
            if item not in ordered_zims:
                ordered_zims.append(item)

        # 1. Try local libzim directly
        try:
            import libzim
            for item in ordered_zims:
                zim_path = item["path"]
                try:
                    archive = libzim.Archive(zim_path)
                    clean_query = query.strip().replace(" ", "_")
                    entry = None
                    for cand in [query.strip(), clean_query, clean_query.title()]:
                        try:
                            entry = archive.get_entry_by_path(cand)
                            if entry:
                                break
                        except Exception:
                            pass
                    
                    if entry:
                        item_obj = entry.get_item()
                        content = item_obj.content.tobytes().decode("utf-8", errors="ignore")
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(content, "html.parser")
                        # Remove script and style elements
                        for s in soup(["script", "style", "noscript", "header", "footer"]):
                            s.decompose()
                        clean_text = ' '.join(soup.get_text().split())[:1500]
                        return {
                            "success": True,
                            "source": f"ZIM Offline ({item['title']})",
                            "title": entry.title,
                            "snippet": clean_text,
                            "zim_file": item["filename"]
                        }
                except Exception:
                    continue
        except Exception:
            pass

        # 2. Try Zim Pro / Kiwix-serve HTTP endpoint if configured
        if api_url:
            clean_api = api_url.rstrip("/")
            try:
                encoded = urllib.parse.quote(query)
                req_url = f"{clean_api}/search?pattern={encoded}&format=json"
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(req_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        if results:
                            top = results[0]
                            return {
                                "success": True,
                                "source": "Zim Pro API",
                                "title": top.get("title", query),
                                "snippet": top.get("snippet", ""),
                                "url": f"{clean_api}/{top.get('url', '')}"
                            }
            except Exception:
                pass

        return {
            "success": False,
            "error": "No offline ZIM files found matching the query. You can download Wikipedia or other ZIM archives in Settings -> ZIM Manager."
        }
