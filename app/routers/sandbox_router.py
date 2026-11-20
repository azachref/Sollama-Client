from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.sandbox.code_runner import CodeRunner

router = APIRouter(prefix="/api/sandbox", tags=["Sandbox"])

class RunCodePayload(BaseModel):
    code: str
    language: Optional[str] = "python"
    timeout_sec: Optional[int] = 10

@router.post("/run")
async def execute_code(payload: RunCodePayload):
    if payload.language.lower() in ["python", "py"]:
        return CodeRunner.run_python(payload.code, timeout_sec=payload.timeout_sec or 10)
    return {
        "success": False,
        "exit_code": -1,
        "stdout": "",
        "stderr": f"Direct server execution for '{payload.language}' is not supported. HTML/JS can be run directly in the browser preview sandbox."
    }
