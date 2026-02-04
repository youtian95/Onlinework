from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Header
from sqlmodel import Session, select
from pydantic import BaseModel
from backend.db import engine
from backend.models import SystemSetting
from backend.core.security import verify_token
from backend.core.config import PUBLIC_DIR
import os
import shutil
from pathlib import Path

router = APIRouter()

class SettingsUpdate(BaseModel):
    course_name: str

def get_session():
    with Session(engine) as session:
        yield session

def verify_admin_token(token: str):
    if not token:
        raise HTTPException(status_code=401, detail="Missing Token")
    try:
        payload = verify_token(token)
        if not payload or payload.get("role") != "admin":
            raise HTTPException(status_code=401, detail="Unauthorized")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

def get_setting(session: Session, key: str, default: str = "") -> str:
    setting = session.exec(select(SystemSetting).where(SystemSetting.key == key)).first()
    return setting.value if setting else default

def set_setting(session: Session, key: str, value: str):
    setting = session.exec(select(SystemSetting).where(SystemSetting.key == key)).first()
    if not setting:
        setting = SystemSetting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value
        session.add(setting)
    session.commit()

@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    return {
        "course_name": get_setting(session, "course_name", "在线作业系统"),
        "cover_image": get_setting(session, "cover_image", "")
    }

@router.put("/admin/settings")
def update_settings(
    update: SettingsUpdate, 
    authorization: str = Header(None),
    session: Session = Depends(get_session)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    token = authorization.replace("Bearer ", "") if "Bearer " in authorization else authorization
    verify_admin_token(token)
    
    set_setting(session, "course_name", update.course_name)
    return {"status": "success"}

@router.post("/admin/cover")
async def upload_cover(
    file: UploadFile = File(...), 
    authorization: str = Header(None),
    session: Session = Depends(get_session)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "") if "Bearer " in authorization else authorization
    verify_admin_token(token)
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file")
        
    ext = os.path.splitext(file.filename)[1]
    if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
         raise HTTPException(status_code=400, detail="Only images allowed")

    filename = f"cover{ext}"
    file_path = os.path.join(PUBLIC_DIR, filename)
    
    content = await file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(content)
        
    url = f"/public/{filename}?t={os.urandom(4).hex()}"
    set_setting(session, "cover_image", url)
    return {"url": url}
