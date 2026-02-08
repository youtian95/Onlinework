from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Header, Form
from sqlmodel import Session, select
from pydantic import BaseModel
from backend.db import engine
from backend.models import Student, Attempt, ProblemState
from backend.services.problems import load_problem_script, PROBLEMS_DIR, get_problem_ranking, get_total_ranking
from backend.core.config import ADMIN_PASSWORD
from backend.core.security import pwd_context, create_access_token, verify_token
import csv
import io
import os
from typing import List, Optional
from datetime import datetime, timezone

router = APIRouter()

class AdminLoginRequest(BaseModel):
    password: str

class UpdateAttemptRequest(BaseModel):
    student_id: str
    problem_id: str
    input_id: str
    attempts: int
    correct: bool = False

class ProblemStateUpdate(BaseModel):
    is_visible: Optional[bool] = None
    deadline: Optional[datetime] = None
    is_deleted: Optional[bool] = None
    is_public_view: Optional[bool] = None

class StudentUpdate(BaseModel):
    is_test: Optional[bool] = None
    enabled: Optional[bool] = None
    is_deleted: Optional[bool] = None

class CreateStudentRequest(BaseModel):
    student_id: str
    name: str = ""
    password: Optional[str] = None
    is_test: bool = False

def get_session():
    with Session(engine) as session:
        yield session

# 管理员鉴权依赖
def verify_admin(
    x_admin_token: str = Header(None),
    authorization: str = Header(None)
):
    token = x_admin_token
    if not token and authorization:
        token = authorization
        if token.startswith("Bearer "):
            token = token.split(" ")[1]

    if not token:
        raise HTTPException(status_code=401, detail="Missing Token")

    payload = verify_token(token)
    if payload and payload.get("role") == "admin":
        return payload
        
    raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/login")
def admin_login(req: AdminLoginRequest):
    if req.password == ADMIN_PASSWORD:
        access_token = create_access_token(data={"sub": "admin", "role": "admin"})
        return {"token": access_token}
    else:
        raise HTTPException(status_code=401, detail="Password incorrect")

@router.post("/students/upload", dependencies=[Depends(verify_admin)])
async def upload_students(file: UploadFile = File(...), session: Session = Depends(get_session)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV file is supported")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "student_id" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must include 'student_id' column")

    inserted = 0
    updated = 0
    errors = 0

    for row in reader:
        student_id = (row.get("student_id") or "").strip()
        if not student_id:
            errors += 1
            continue

        name = (row.get("name") or "").strip() or None
        enabled_raw = (row.get("enabled") or "").strip().lower()
        if enabled_raw in ("0", "false", "no", "n"):
            enabled = False
        else:
            enabled = True

        student = session.exec(
            select(Student).where(Student.student_id == student_id)
        ).first()

        if student:
            student.name = name
            student.enabled = enabled
            updated += 1
        else:
            student = Student(
                student_id=student_id,
                name=name,
                enabled=enabled,
            )
            session.add(student)
            inserted += 1

    session.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "message": "Upload processed"
    }

@router.post("/problems/upload", dependencies=[Depends(verify_admin)])
async def upload_problem(
    problem_id: str = Form(...),
    files: List[UploadFile] = File(...),
    main_script: str = Form(...),
    main_md: str = Form(...),
    session: Session = Depends(get_session)
):
    # Security checks
    if not problem_id or ".." in problem_id or "/" in problem_id or "\\" in problem_id:
         raise HTTPException(status_code=400, detail="Invalid problem_id")

    problem_dir = os.path.join(PROBLEMS_DIR, problem_id)
    os.makedirs(problem_dir, exist_ok=True)
    
    saved_files = []

    for file in files:
        filename = file.filename
        if not filename: continue
        
        # Path traversal check
        if ".." in filename or "/" in filename or "\\" in filename:
             continue 
        
        target_name = filename
        
        # Rename logic
        if filename == main_script:
            target_name = "script.py"
        elif filename == main_md:
            target_name = "problem.md"
            
        file_path = os.path.join(problem_dir, target_name)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        saved_files.append(target_name)
    
    if "script.py" not in saved_files:
         raise HTTPException(status_code=400, detail="Missing main script (script.py)")
    if "problem.md" not in saved_files:
         raise HTTPException(status_code=400, detail="Missing main markdown (problem.md)")

    # Init DB state
    script = load_problem_script(problem_id)
    title = problem_id
    if script and hasattr(script, "meta"):
        title = script.meta.get("title", problem_id)

    # Update or create state
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    if not state:
        state = ProblemState(problem_id=problem_id, title=title, is_visible=False)
        session.add(state)
    else:
        state.title = title # Update title if changed
        # Keep existing visible/deadline/deleted states
        pass
    
    session.commit()

    return {"message": f"Problem {problem_id} uploaded successfully with {len(saved_files)} files"}

@router.put("/problems/{problem_id}/state", dependencies=[Depends(verify_admin)])
def update_problem_state(
    problem_id: str, 
    update: ProblemStateUpdate, 
    session: Session = Depends(get_session)
):
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    if not state:
        # Lazy creation if not exists (e.g. for existing problems)
        state = ProblemState(problem_id=problem_id, is_visible=False)
        session.add(state)
    
    # Use exclude_unset to distinguish between "not provided" and "provided as null"
    # This supports setting deadline to None (removing it)
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(state, key, value)
    
    # Logic: If unpublishing (setting is_visible to False), automatically clear the deadline
    # This ensures that when a problem is hidden, it doesn't keep a deadline that might expire quietly.
    if update.is_visible is False:
        state.deadline = None

    session.commit()
    session.refresh(state)

    # Ensure timezone info is returned
    if state.deadline and state.deadline.tzinfo is None:
        state.deadline = state.deadline.replace(tzinfo=timezone.utc)
        
    return state


@router.get("/students", dependencies=[Depends(verify_admin)])
def list_students(deleted_only: bool = False, session: Session = Depends(get_session)):
    query = select(Student)
    if deleted_only:
        query = query.where(Student.is_deleted == True)
    else:
        query = query.where(Student.is_deleted == False) # Default to showing active students
    students = session.exec(query).all()
    return students

@router.post("/students", dependencies=[Depends(verify_admin)])
def create_student(req: CreateStudentRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(Student).where(Student.student_id == req.student_id)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student ID already exists")
    
    pwd_hash = None
    if req.password:
        pwd_hash = pwd_context.hash(req.password)
        
    student = Student(
        student_id=req.student_id,
        name=req.name,
        is_test=req.is_test,
        password_hash=pwd_hash,
        enabled=True
    )
    session.add(student)
    session.commit()
    session.refresh(student)
    return student

@router.put("/students/{student_id}", dependencies=[Depends(verify_admin)])
def update_student(student_id: str, update: StudentUpdate, session: Session = Depends(get_session)):
    student = session.exec(select(Student).where(Student.student_id == student_id)).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    if update.is_test is not None:
        student.is_test = update.is_test
    if update.enabled is not None:
        student.enabled = update.enabled
    if update.is_deleted is not None:
        student.is_deleted = update.is_deleted
        
    session.add(student)
    session.commit()
    session.refresh(student)
    return student

@router.delete("/students/{student_id}", dependencies=[Depends(verify_admin)])
def delete_student(student_id: str, session: Session = Depends(get_session)):
    student = session.exec(select(Student).where(Student.student_id == student_id)).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student.is_deleted = True
    session.add(student)
    session.commit()
    return {"message": "Moved to recycle bin"}

@router.get('/students/{student_id}/progress', dependencies=[Depends(verify_admin)])
def get_student_progress(student_id: str, session: Session = Depends(get_session)):
    problems_data = []
    
    if not os.path.exists(PROBLEMS_DIR):
        return []

    # 1. 获取所有题目文件夹
    problem_folders = [f for f in os.listdir(PROBLEMS_DIR) if os.path.isdir(os.path.join(PROBLEMS_DIR, f))]
    
    # 2. 获取该学生的所有尝试记录
    attempts = session.exec(select(Attempt).where(Attempt.student_id == student_id)).all()
    # 转为字典映射: (problem_id, input_id) -> Attempt对象
    attempts_map = {(a.problem_id, a.input_id): a for a in attempts}

    # Filter out deleted problems
    deleted_ids = session.exec(select(ProblemState.problem_id).where(ProblemState.is_deleted == True)).all()
    deleted_set = set(deleted_ids)

    for problem_id in problem_folders:
        if problem_id in deleted_set:
            continue

        script = load_problem_script(problem_id)
        if not script or not hasattr(script, 'meta'):
            continue
            
        meta = script.meta
        title = meta.get('title', problem_id)
        inputs_meta = meta.get('inputs', {})
        
        problem_inputs = {}
        
        # 遍历题目配置的输入项
        for input_id, config in inputs_meta.items():
            max_attempts = config.get('max_attempts', 1)
            
            # 获取用户的尝试记录
            attempt_record = attempts_map.get((problem_id, input_id))
            used_attempts = attempt_record.attempts if attempt_record else 0
            is_correct = attempt_record.correct if attempt_record else False
            
            problem_inputs[input_id] = {
                'attempts': used_attempts,
                'max_attempts': max_attempts,
                'correct': is_correct
            }
            
        problems_data.append({
            'id': problem_id,
            'title': title,
            'inputs': problem_inputs
        })
        
    return problems_data

@router.post('/attempts/update', dependencies=[Depends(verify_admin)])
def update_attempt(req: UpdateAttemptRequest, session: Session = Depends(get_session)):
    # 查找记录
    attempt = session.exec(
        select(Attempt).where(
            Attempt.student_id == req.student_id,
            Attempt.problem_id == req.problem_id,
            Attempt.input_id == req.input_id
        )
    ).first()
    
    if not attempt:
        # 如果尝试次数为0且未正确，无需创建记录
        if req.attempts == 0 and not req.correct:
            return {'message': 'No change needed'}
            
        # 创建新记录
        attempt = Attempt(
            student_id=req.student_id,
            problem_id=req.problem_id,
            input_id=req.input_id,
            attempts=req.attempts,
            correct=req.correct
        )
        session.add(attempt)
    else:
        attempt.attempts = req.attempts
        attempt.correct = req.correct
        
    session.commit()
    return {'message': 'Updated successfully'}

@router.get('/problems', dependencies=[Depends(verify_admin)])
def list_admin_problems(session: Session = Depends(get_session)):
    problems = []
    if not os.path.exists(PROBLEMS_DIR):
        return []
    
    # Pre-fetch all states
    states = session.exec(select(ProblemState)).all()
    states_map = {s.problem_id: s for s in states}
        
    for name in os.listdir(PROBLEMS_DIR):
        script = load_problem_script(name)
        if script and hasattr(script, "meta"):
            # Ensure state exists
            state = states_map.get(name)
            if not state:
                state_dict = {
                    "is_visible": False,
                    "deadline": None,
                    "is_deleted": False,
                    "is_public_view": False
                }
            else:
                # Ensure deadline is timezone aware (UTC) if it's naive
                deadline = state.deadline
                if deadline and deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                
                state_dict = {
                    "is_visible": state.is_visible,
                    "deadline": deadline,
                    "is_deleted": state.is_deleted,
                    "is_public_view": state.is_public_view
                }

            problems.append({
                "id": name,
                "title": script.meta.get("title", name),
                **state_dict
            })
    return problems

@router.get('/problems/{problem_id}/ranking', dependencies=[Depends(verify_admin)])
def get_admin_ranking(problem_id: str, session: Session = Depends(get_session)):
    return get_problem_ranking(session, problem_id)

@router.get('/ranking', dependencies=[Depends(verify_admin)])
def get_admin_total_ranking(session: Session = Depends(get_session)):
    return get_total_ranking(session)
