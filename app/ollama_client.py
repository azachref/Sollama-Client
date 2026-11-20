import json
import httpx
import re
from typing import AsyncGenerator, Dict, Any, List, Optional
from app.database import get_setting

class OllamaClient:
    """Async client for interacting with Ollama API."""

    @classmethod
    def get_base_url(cls) -> str:
        url = get_setting("ollama_base_url", "http://127.0.0.1:11434")
        return url.rstrip("/")

    @classmethod
    async def check_health(cls) -> Dict[str, Any]:
        """Test Ollama connection and return status."""
        base_url = cls.get_base_url()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{base_url}/api/tags")
                if res.status_code == 200:
                    models = [m["name"] for m in res.json().get("models", [])]
                    return {"connected": True, "base_url": base_url, "models": models}
                return {"connected": False, "base_url": base_url, "error": f"HTTP {res.status_code}"}
        except Exception as e:
            return {"connected": False, "base_url": base_url, "error": str(e)}

    @classmethod
    async def list_models(cls) -> List[Dict[str, Any]]:
        """Fetch list of installed models in Ollama."""
        base_url = cls.get_base_url()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{base_url}/api/tags")
                if res.status_code == 200:
                    return res.json().get("models", [])
                return []
        except Exception:
            return []

    @classmethod
    async def get_embedding(cls, text: str, model_name: Optional[str] = None) -> List[float]:
        """Generate vector embedding for text using Ollama."""
        base_url = cls.get_base_url()
        if not model_name:
            model_name = get_setting("default_embedding_model", "nomic-embed-text:latest")
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Modern Ollama uses /api/embed, fallback to /api/embeddings
                payload = {"model": model_name, "input": text}
                res = await client.post(f"{base_url}/api/embed", json=payload)
                if res.status_code == 200:
                    embeddings = res.json().get("embeddings", [])
                    if embeddings and len(embeddings) > 0:
                        return embeddings[0]
                
                # Fallback to older /api/embeddings
                payload2 = {"model": model_name, "prompt": text}
                res2 = await client.post(f"{base_url}/api/embeddings", json=payload2)
                if res2.status_code == 200:
                    return res2.json().get("embedding", [])
        except Exception:
            pass
        return []

    @classmethod
    async def stream_chat(
        cls,
        messages: List[Dict[str, Any]],
        model: str,
        options: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from Ollama.
        Yields dicts with:
        - type: "chunk" | "thinking" | "done" | "error"
        - content: str
        """
        base_url = cls.get_base_url()

        # Build payload
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        for m in messages:
            msg_obj = {"role": m["role"], "content": m["content"]}
            if "images" in m and m["images"]:
                msg_obj["images"] = m["images"]
            formatted_messages.append(msg_obj)

        default_options = {
            "temperature": float(get_setting("temperature", 0.7)),
            "top_p": float(get_setting("top_p", 0.9)),
            "top_k": int(get_setting("top_k", 40)),
            "repeat_penalty": float(get_setting("repeat_penalty", 1.1)),
            "num_ctx": int(get_setting("num_ctx", 4096))
        }
        if options:
            default_options.update(options)

        payload = {
            "model": model,
            "messages": formatted_messages,
            "stream": True,
            "options": default_options
        }

        in_thinking_mode = False
        full_buffer = ""

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", f"{base_url}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        err_text = await response.aread()
                        yield {
                            "type": "error",
                            "error": f"Ollama error (HTTP {response.status_code}): {err_text.decode('utf-8', errors='ignore')}"
                        }
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            delta = data.get("message", {}).get("content", "")
                            is_done = data.get("done", False)

                            if delta:
                                full_buffer += delta

                                # Check for thinking tags <think> and </think>
                                if "<think>" in full_buffer and not in_thinking_mode:
                                    in_thinking_mode = True
                                    # Output whatever was before <think>
                                    parts = full_buffer.split("<think>", 1)
                                    if parts[0]:
                                        yield {"type": "content", "content": parts[0]}
                                    full_buffer = parts[1]

                                if in_thinking_mode:
                                    if "</think>" in full_buffer:
                                        think_parts = full_buffer.split("</think>", 1)
                                        yield {"type": "thinking", "content": think_parts[0]}
                                        in_thinking_mode = False
                                        full_buffer = think_parts[1]
                                        if full_buffer:
                                            yield {"type": "content", "content": full_buffer}
                                            full_buffer = ""
                                    else:
                                        # Yield thinking delta
                                        yield {"type": "thinking", "content": delta}
                                else:
                                    yield {"type": "content", "content": delta}

                            if is_done:
                                yield {"type": "done", "total_duration": data.get("total_duration", 0)}
                                return

                        except Exception as parse_err:
                            continue
        except httpx.ConnectError:
            yield {
                "type": "error",
                "error": f"Could not connect to Ollama at {base_url}. Please ensure Ollama is running (`ollama serve`)."
            }
        except Exception as e:
            yield {"type": "error", "error": f"Ollama streaming exception: {str(e)}"}
