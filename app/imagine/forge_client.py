import base64
import uuid
import httpx
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import GENERATED_IMAGES_DIR
from app.database import get_db, get_setting

class SDForgeClient:
    """Client for Stable Diffusion WebUI / Forge Neo API."""

    @classmethod
    def get_api_url(cls) -> str:
        return get_setting("sd_forge_url", "http://127.0.0.1:7860").rstrip("/")

    @classmethod
    async def check_status(cls) -> Dict[str, Any]:
        """Test connection and list models."""
        url = cls.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{url}/sdapi/v1/sd-models")
                if res.status_code == 200:
                    models = [m.get("model_name", m.get("title", "")) for m in res.json()]
                    return {"connected": True, "url": url, "models": models}
                return {"connected": False, "url": url, "error": f"HTTP {res.status_code}"}
        except Exception as e:
            return {"connected": False, "url": url, "error": str(e)}

    @classmethod
    async def get_models(cls) -> List[Dict[str, Any]]:
        url = cls.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{url}/sdapi/v1/sd-models")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return []

    @classmethod
    async def get_vaes(cls) -> List[Dict[str, Any]]:
        url = cls.get_api_url()
        vaes = [{"model_name": "Automatic"}, {"model_name": "None"}]
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{url}/sdapi/v1/sd-vae")
                if res.status_code == 200:
                    for v in res.json():
                        name = v.get("model_name")
                        if name and name not in ["Automatic", "None"]:
                            vaes.append(v)
        except Exception:
            pass
        return vaes

    @classmethod
    async def get_text_encoders(cls) -> List[str]:
        """List common text encoders supported by Forge Neo / SD3 / Flux."""
        encoders = ["None", "Automatic", "CLIP-L", "CLIP-G", "T5-XXL", "Dual CLIP (SDXL)", "Triple Encoder (SD3)"]
        url = cls.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{url}/sdapi/v1/sd-modules")
                if res.status_code == 200:
                    for m in res.json():
                        t = m.get("model_name")
                        if t and t not in encoders:
                            encoders.append(t)
        except Exception:
            pass
        return encoders

    @classmethod
    async def get_loras(cls) -> List[Dict[str, Any]]:
        url = cls.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{url}/sdapi/v1/loras")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        return []

    @classmethod
    async def get_samplers(cls) -> List[Dict[str, Any]]:
        url = cls.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{url}/sdapi/v1/samplers")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        # Default fallback samplers
        return [{"name": s} for s in ["Euler a", "Euler", "DPM++ 2M Karras", "DPM++ SDE Karras", "UniPC", "DDIM"]]

    @classmethod
    async def get_schedulers(cls) -> List[Dict[str, Any]]:
        url = cls.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{url}/sdapi/v1/schedulers")
                if res.status_code == 200:
                    return res.json()
        except Exception:
            pass
        # Default fallback schedulers
        return [{"name": s} for s in ["Simple", "Karras", "Exponential", "SGM Uniform", "Beta"]]

    @classmethod
    async def set_options(cls, options: Dict[str, Any]) -> bool:
        """Update active checkpoint or VAE on the Forge server."""
        url = cls.get_api_url()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(f"{url}/sdapi/v1/options", json=options)
                return res.status_code == 200
        except Exception:
            return False

    @classmethod
    async def generate_image(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send txt2img generation request to Stable Diffusion Forge Neo.
        Saves resulting image and records into history database.
        """
        url = cls.get_api_url()

        # Update options if specified
        opt_payload = {}
        if params.get("checkpoint"):
            opt_payload["sd_model_checkpoint"] = params["checkpoint"]
        
        vae_val = params.get("vae", "Automatic")
        if vae_val == "None":
            opt_payload["sd_vae"] = "None"
        elif vae_val and vae_val != "Automatic":
            opt_payload["sd_vae"] = vae_val

        clip_skip = params.get("clip_skip")
        if clip_skip:
            opt_payload["CLIP_stop_at_last_layers"] = int(clip_skip)

        if opt_payload:
            await cls.set_options(opt_payload)

        # Build prompt, incorporating any LoRAs if provided
        final_prompt = params.get("prompt", "")
        loras = params.get("loras", [])
        if isinstance(loras, list):
            for lora in loras:
                lname = lora.get("name")
                lweight = lora.get("weight", 1.0)
                if lname:
                    final_prompt += f" <lora:{lname}:{lweight}>"

        txt2img_payload = {
            "prompt": final_prompt,
            "negative_prompt": params.get("negative_prompt", get_setting("sd_negative_prompt", "")),
            "steps": int(params.get("steps", get_setting("sd_steps", 25))),
            "cfg_scale": float(params.get("cfg_scale", get_setting("sd_cfg_scale", 7.0))),
            "width": int(params.get("width", get_setting("sd_width", 1024))),
            "height": int(params.get("height", get_setting("sd_height", 1024))),
            "sampler_name": params.get("sampler_name", get_setting("sd_sampler_name", "Euler a")),
            "seed": int(params.get("seed", -1)),
            "batch_size": 1,
            "n_iter": 1
        }

        # Extra parameters for Forge Neo / Flux / Flow match models
        if params.get("scheduler"):
            txt2img_payload["scheduler"] = params["scheduler"]
        if params.get("shift"):
            txt2img_payload["distilled_cfg_scale"] = float(params["shift"])
            txt2img_payload["guidance_scale"] = float(params["shift"])

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                res = await client.post(f"{url}/sdapi/v1/txt2img", json=txt2img_payload)
                if res.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Forge API returned HTTP {res.status_code}: {res.text}"
                    }

                data = res.json()
                images = data.get("images", [])
                if not images:
                    return {"success": False, "error": "No images returned by SD Forge"}

                # Save primary image
                img_data = images[0]
                img_bytes = base64.b64decode(img_data)
                img_filename = f"sd_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}.png"
                img_path = GENERATED_IMAGES_DIR / img_filename
                
                with open(img_path, "wb") as f:
                    f.write(img_bytes)

                # Record in database
                img_id = str(uuid.uuid4())
                now = datetime.now().isoformat()
                conn = get_db()
                conn.execute("""
                    INSERT INTO image_history (id, prompt, negative_prompt, model, sampler, steps, cfg, shift, seed, width, height, image_filename, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    img_id,
                    final_prompt,
                    txt2img_payload["negative_prompt"],
                    params.get("checkpoint", ""),
                    txt2img_payload["sampler_name"],
                    txt2img_payload["steps"],
                    txt2img_payload["cfg_scale"],
                    float(params.get("shift", 1.0)),
                    txt2img_payload["seed"],
                    txt2img_payload["width"],
                    txt2img_payload["height"],
                    img_filename,
                    now
                ))
                conn.commit()
                conn.close()

                return {
                    "success": True,
                    "id": img_id,
                    "image_url": f"/api/imagine/image/{img_filename}",
                    "filename": img_filename,
                    "prompt": final_prompt,
                    "width": txt2img_payload["width"],
                    "height": txt2img_payload["height"],
                    "seed": txt2img_payload["seed"],
                    "created_at": now
                }

        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"Failed to connect to Stable Diffusion Forge at {url}. Make sure Forge is running with --api flag."
            }
        except Exception as e:
            return {"success": False, "error": f"Image generation error: {str(e)}"}
