from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.requests import Request
from pydantic import BaseModel
from typing import Optional, List
from fastapi.responses import JSONResponse, FileResponse
import os
import json
from env_manager import EnvManager
import base64
import traceback
import time


# ------------------------
# Data models for request bodies
# ------------------------


class CreateEnvRequest(BaseModel):
    config_path: str = "config.yaml"


class ScreenshotRequest(BaseModel):
    env_id: str
    prefix: Optional[str] = None
    suffix: Optional[str] = "before"


class StepRequest(BaseModel):
    env_id: str
    action: str
    element: Optional[List[float]] = None
    kwargs: Optional[dict] = None


class StopRequest(BaseModel):
    env_id: str


class GetXmlRequest(BaseModel):
    env_id: str


class StartRecordRequest(BaseModel):
    env_id: str


class EndRecordRequest(BaseModel):
    env_id: str


class ResetRequest(BaseModel):
    env_id: str
    app_name: Optional[str] = None


# ------------------------
# Create application & EnvManager singleton
# ------------------------

app = FastAPI()
env_manager = EnvManager()


# ------------------------
# Global HTTPException handler: unify response format
# ------------------------
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code, content={"success": False, "message": exc.detail}
    )


# ------------------------
# Route definitions
# ------------------------


@app.post("/create_env")
async def create_env(file: UploadFile = File(...)):
    """
    Upload a JSON file, parse it to dict, call EnvManager.create_env
    to initialize an environment and return the environment ID.
    """
    try:
        content = await file.read()
        config_dict = json.loads(content.decode("utf-8"))
        env_id = env_manager.create_env(config_dict)
        print(env_id)
        return JSONResponse(content={"success": True, "env_id": env_id})
    except Exception as e:
        print("create_env error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/screenshot")
def get_screenshot(request: ScreenshotRequest):
    """Get environment screenshot and return Base64 encoded JSON data."""
    try:
        screenshot_path = env_manager.get_screenshot(
            env_id=request.env_id, prefix=request.prefix, suffix=request.suffix
        )
        if not os.path.exists(screenshot_path):
            raise HTTPException(status_code=404, detail="Screenshot file not found")
        with open(screenshot_path, "rb") as f:
            binary_data = f.read()
        encoded_data = base64.b64encode(binary_data).decode("utf-8")
        return {"success": True, "screenshot": encoded_data}
    except Exception as e:
        print("screenshot error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/step")
def step(request: StepRequest):
    """
    Execute an action (e.g. Tap, Swipe, InputText, ...)
    - action: action name string
    - element: optional coordinate list like [x, y]
    - kwargs: other optional keyword parameters
    """
    try:
        env_manager.step(
            env_id=request.env_id,
            action=request.action,
            element=request.element,
            **(request.kwargs if request.kwargs else {})
        )
        return {"success": True, "message": "action_performed"}
    except Exception as e:
        print("step error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/get_screen_size")
def get_screen_size(request: ScreenshotRequest):
    """Get screen size."""
    try:
        screen_size = env_manager.get_screen_size(request.env_id)
        return {"success": True, "screen_size": screen_size}
    except Exception as e:
        print("get_screen_size error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/stop_env")
def stop_env(request: StopRequest):
    """Stop and destroy the environment."""
    try:
        env_manager.stop(request.env_id)
        return {"success": True, "message": "env_stopped"}
    except Exception as e:
        print("stop_env error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/get_xml")
def get_xml(request: GetXmlRequest):
    """Get current page XML and return as JSON data."""
    try:
        xml_path = env_manager.get_xml(request.env_id)
        if xml_path == "ERROR":
            raise HTTPException(status_code=500, detail="Failed to get XML")
        if not os.path.exists(xml_path):
            raise HTTPException(status_code=404, detail="XML file not found")
        with open(xml_path, "r", encoding="utf-8") as f:
            xml_content = f.read()
        return {"success": True, "xml": xml_content}
    except Exception as e:
        print("get_xml error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/start_record")
def start_record(request: StartRecordRequest):
    """Start recording current environment operations."""
    try:
        env_manager.start_record(request.env_id)
        time.sleep(3)
        return {"success": True, "message": "recording_started"}
    except Exception as e:
        print("start_record error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/end_record")
def end_record(request: EndRecordRequest):
    """Stop recording and return the recorded video file."""
    try:
        rel_record_path = env_manager.end_record(request.env_id)
        abs_record_path = os.path.abspath(rel_record_path)
        print("absolute path:", abs_record_path)
        if not os.path.exists(abs_record_path):
            raise HTTPException(status_code=404, detail="Record file not found")

        return FileResponse(
            path=abs_record_path,
            media_type="video/mp4",
            filename=os.path.basename(abs_record_path),
        )
    except Exception as e:
        print("end_record error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/reset")
def reset_env(request: ResetRequest):
    """Reset the current environment."""
    try:
        env_manager.reset(request.env_id, app_name=request.app_name)
        return {"success": True, "message": "env_reset"}
    except Exception as e:
        print("reset_env error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
