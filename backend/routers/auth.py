from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from backend.db import engine
from backend.models import Student
from backend.core.security import pwd_context, create_access_token

router = APIRouter()

class AuthCheckResponse(BaseModel):
    status: str  # 'setup_required', 'login_required', 'unknown'
    name: str = None

class LoginRequest(BaseModel):
    student_id: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    name: str

def get_session():
    with Session(engine) as session:
        yield session

@router.get("/check", response_model=AuthCheckResponse)
def check_student_status(student_id: str, session: Session = Depends(get_session)):
    student = session.exec(
        select(Student).where(Student.student_id == student_id)
    ).first()
    
    if not student or student.is_deleted:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if not student.enabled:
        raise HTTPException(status_code=403, detail="Student disabled")
        
    status = "setup_required" if not student.password_hash else "login_required"
    return {"status": status, "name": student.name}

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, session: Session = Depends(get_session)):
    student = session.exec(
        select(Student).where(Student.student_id == req.student_id)
    ).first()
    
    if not student or student.is_deleted:
        # Avoid user enumeration, though error message hints exist elsewhere
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not student.password_hash:
        raise HTTPException(status_code=401, detail="Account not set up")

    if not pwd_context.verify(req.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not student.enabled:
        raise HTTPException(status_code=403, detail="Account disabled")
        
    access_token = create_access_token(data={"sub": student.student_id, "role": "student"})
    return {"access_token": access_token, "token_type": "bearer", "name": student.name} 

@router.post("/setup")
def setup_password(req: LoginRequest, session: Session = Depends(get_session)):
    student = session.exec(
        select(Student).where(Student.student_id == req.student_id)
    ).first()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    if student.password_hash:
        raise HTTPException(status_code=400, detail="Password already set")
    
    student.password_hash = pwd_context.hash(req.password)
    session.add(student)
    session.commit()
    
    return {"message": "Password set successfully"}
