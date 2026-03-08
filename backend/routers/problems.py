from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import Dict, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import re
import uuid
import shutil
from pathlib import Path

from backend.db import engine
from backend.models import Student, Attempt, ProblemState, ProblemSubmission
from backend.utils import get_stable_rng
from backend.core.security import verify_token
from backend.core.config import PUBLIC_DIR
from backend.services.problems import (
    load_problem_script, 
    require_student, 
    get_problem_content_and_status, 
    PROBLEMS_DIR,
    build_attempt_status,
    get_problem_ranking,
    get_total_ranking,
    collect_input_ids,
    ensure_meta_inputs,
    DEFAULT_INPUT_SCORE,
    DEFAULT_MAX_ATTEMPTS,
    get_problem_input_ids
)

router = APIRouter()
SUBMISSIONS_DIR = PUBLIC_DIR / "submissions"


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return cleaned or "unknown"


def _save_submission_pdf(student_id: str, problem_id: str, pdf_file: UploadFile):
    filename = pdf_file.filename or "submission.pdf"
    ext = Path(filename).suffix.lower()
    content_type = (pdf_file.content_type or "").lower()
    if ext != ".pdf" and content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    target_dir = SUBMISSIONS_DIR / _safe_name(problem_id) / _safe_name(student_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}.pdf"
    full_path = target_dir / saved_name

    pdf_file.file.seek(0)
    with open(full_path, "wb") as f:
        shutil.copyfileobj(pdf_file.file, f)

    rel_path = full_path.relative_to(PUBLIC_DIR).as_posix()
    return rel_path, filename


def _upsert_submission_record(
    session: Session,
    student_id: str,
    problem_id: str,
    pdf_path: str,
    original_filename: str,
):
    record = session.exec(
        select(ProblemSubmission).where(
            ProblemSubmission.student_id == student_id,
            ProblemSubmission.problem_id == problem_id,
        )
    ).first()

    if record and record.pdf_path:
        old_path = PUBLIC_DIR / record.pdf_path
        if old_path.exists() and old_path.is_file() and old_path != (PUBLIC_DIR / pdf_path):
            try:
                old_path.unlink()
            except OSError:
                pass

    if not record:
        record = ProblemSubmission(student_id=student_id, problem_id=problem_id, pdf_path=pdf_path)
        session.add(record)

    record.pdf_path = pdf_path
    record.original_filename = original_filename
    record.updated_at = datetime.now(timezone.utc)
    return record


class SubmitRequest(BaseModel):
    # student_id optional/ignored in payload because we get it from token
    # But for compatibility, if frontend sends it, we might check consistency or ignore.
    student_id: Optional[str] = None 
    problem_id: str
    answers: Dict[str, str]

def get_session():
    with Session(engine) as session:
        yield session

def get_optional_current_student(
    authorization: Optional[str] = Header(None), 
    session: Session = Depends(get_session)
) -> Optional[Student]:
    """Dependency that returns a Student if token is valid, else None"""
    if not authorization:
        return None
    
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    else:
        token = authorization
        
    payload = verify_token(token)
    if not payload:
        return None
        
    student_id = payload.get("sub")
    if not student_id:
        return None
    
    student = session.exec(select(Student).where(Student.student_id == student_id)).first()
    if not student or not student.enabled:
        return None
        
    return student

def get_current_student(
    authorization: str = Header(None), 
    session: Session = Depends(get_session)
) -> Student:
    """Dependency to parse JWT and get current student"""
    if not authorization:
        print("DEBUG: Missing Authorization Header")
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    # Support "Bearer <token>"
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    else:
        # Or just raw token
        token = authorization
        
    payload = verify_token(token)
    if not payload:
        print(f"DEBUG: Token verification failed. Token: {token[:10]}...")
        raise HTTPException(status_code=401, detail="Invalid Token")
        
    student_id = payload.get("sub")
    if not student_id:
        print("DEBUG: No sub in payload")
        raise HTTPException(status_code=401, detail="Invalid Token Payload")
    
    print(f"DEBUG: Looking for student {student_id}")
    student = session.exec(select(Student).where(Student.student_id == student_id)).first()
    if not student:
        print(f"DEBUG: Student {student_id} not found in DB")
        # 尝试列出所有学生以便调试
        all_students = session.exec(select(Student)).all()
        print(f"DEBUG: Existing students: {[s.student_id for s in all_students]}")
        raise HTTPException(status_code=401, detail="User not found")
        
    if not student.enabled:
        raise HTTPException(status_code=403, detail="Account disabled")
        
    return student


@router.get("")
def list_problems(
    current_student: Optional[Student] = Depends(get_optional_current_student), 
    session: Session = Depends(get_session)
):
    student_id = current_student.student_id if current_student else None
    problems = []
    if not os.path.exists(PROBLEMS_DIR):
        return []

    # Get problem states
    states = session.exec(select(ProblemState)).all()
    states_dict = {s.problem_id: s for s in states}

    # 预先获取该学生的所有尝试记录，减少数据库查询
    attempts_map = {}
    if student_id:
        student_attempts = session.exec(select(Attempt).where(Attempt.student_id == student_id)).all()
        for a in student_attempts:
            attempts_map[(a.problem_id, a.input_id)] = a
        
    for name in os.listdir(PROBLEMS_DIR):
        # 1. Check Visibility & Deletion
        state = states_dict.get(name)
        
        # Default policy: problems without explicit state are UNPUBLISHED
        is_visible = state.is_visible if state else False
        is_deleted = state.is_deleted if state else False
        is_public_view = state.is_public_view if state else False
        
        if is_deleted or not is_visible:
            continue

        # If User is not logged in, only show public view problems
        if not student_id and not is_public_view:
             continue

        deadline = state.deadline if state else None
        if deadline and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        is_terminated = False
        if deadline and datetime.now(timezone.utc) > deadline:
             is_terminated = True

        script = load_problem_script(name)
        if script and hasattr(script, "meta"):
            # 计算分数
            meta = ensure_meta_inputs(script.meta)
            meta_inputs = meta.get("inputs", {})
            total_score = 0
            obtained_score = 0
            
            # Use template rendering to find all input IDs, same as in get_problem logic
            if student_id:
                seed = f"{student_id}_{name}"
            else:
                seed = f"public_{name}"
            
            
            input_ids = get_problem_input_ids(name, script)
            
            for input_id in input_ids:
                config = meta_inputs.get(input_id, {})
                s = config.get("score", DEFAULT_INPUT_SCORE)
                total_score += s
                
                # 如果有记录且正确，则加分
                if student_id:
                    attempt = attempts_map.get((name, input_id))
                    if attempt and attempt.correct:
                        obtained_score += s

            problems.append({
                "id": name,
                "title": script.meta.get("title", name),
                "total_score": total_score,
                "obtained_score": obtained_score,
                "is_terminated": is_terminated,
                "deadline": deadline
            })
    return problems

@router.get("/ranking")
def get_all_ranking(
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    return get_total_ranking(session)

@router.get("/{problem_id}")
def get_problem(
    problem_id: str, 
    current_student: Optional[Student] = Depends(get_optional_current_student),
    session: Session = Depends(get_session)
):
    student_id = current_student.student_id if current_student else None
    
    # Check access
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    if state:
        if state.is_deleted:
            raise HTTPException(status_code=404, detail="Problem not found")
        if not state.is_visible:
            raise HTTPException(status_code=403, detail="Problem not published")
        
        # Guest Access Check
        if not student_id and not state.is_public_view:
            raise HTTPException(status_code=403, detail="Access denied for guests")
            
    content = get_problem_content_and_status(session, problem_id, student_id)
    
    # Inject deadline info into the response if possible, 
    # but get_problem_content_and_status returns a dict or templated HTML.
    # Actually looking at services/problems.py, it returns a dict with "html", "status", etc.
    # We can inject "is_terminated" there.
    
    is_terminated = False
    deadline = None
    
    if state and state.deadline:
         deadline = state.deadline
         if deadline.tzinfo is None:
             deadline = deadline.replace(tzinfo=timezone.utc)

         if datetime.now(timezone.utc) > deadline:
             is_terminated = True
             
    if isinstance(content, dict):
        submission = None
        if student_id:
            submission = session.exec(
                select(ProblemSubmission).where(
                    ProblemSubmission.student_id == student_id,
                    ProblemSubmission.problem_id == problem_id,
                )
            ).first()

        content["is_terminated"] = is_terminated
        content["deadline"] = deadline
        content["pdf_uploaded"] = bool(submission)
        content["pdf_filename"] = submission.original_filename if submission else None
            
    return content

@router.post("/submit")
# 注意：原始 API 是 /submit，而不是 /problems/submit。
# 为了保持路由模块的独立性，我们在这里定义，但在 main.py 中我们会单独处理挂载
# 以兼容前端直接请求 /submit 的情况
def submit_answer_endpoint(
    req: SubmitRequest,
    current_student: Optional[Student] = Depends(get_optional_current_student),
    session: Session = Depends(get_session)
):
    # Enforce student_id from token if available, otherwise None for guest
    req.student_id = current_student.student_id if current_student else None

    return submit_answer(req, session)


@router.post("/{problem_id}/pdf")
async def upload_problem_pdf(
    problem_id: str,
    pdf: UploadFile = File(...),
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session),
):
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    if state:
        if state.is_deleted:
            raise HTTPException(status_code=404, detail="Problem not found")
        if not state.is_visible:
            raise HTTPException(status_code=403, detail="Problem not available")

    script = load_problem_script(problem_id)
    if not script:
        raise HTTPException(status_code=404, detail="Problem not found")

    try:
        saved_pdf_path, original_filename = _save_submission_pdf(current_student.student_id, problem_id, pdf)
        _upsert_submission_record(
            session,
            current_student.student_id,
            problem_id,
            saved_pdf_path,
            original_filename,
        )
        session.commit()
    finally:
        await pdf.close()

    return {
        "message": "PDF uploaded",
        "pdf_uploaded": True,
        "pdf_filename": original_filename,
    }


@router.get("/{problem_id}/ranking")
def get_ranking(
    problem_id: str, 
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    return get_problem_ranking(session, problem_id)


def submit_answer(req: SubmitRequest, session: Session):
    # 0. Check Lifecycle
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == req.problem_id)).first()
    if state:
        if state.is_deleted:
             raise HTTPException(status_code=404, detail="Problem not found")
        if not state.is_visible:
             raise HTTPException(status_code=403, detail="Problem not available")
        # Check guest access if no student_id
        if not req.student_id and not state.is_public_view:
             raise HTTPException(status_code=403, detail="Guest submission not allowed")
             
        if state.deadline:
             if datetime.now(timezone.utc) > state.deadline.replace(tzinfo=timezone.utc):
                 raise HTTPException(status_code=400, detail="Submission deadline passed")

    # 1. 加载脚本
    script = load_problem_script(req.problem_id)
    if not script:
        raise HTTPException(status_code=404, detail="Problem not found")

    # 2. 重新生成参数
    # Use fixed seed for guests
    seed = f"{req.student_id}_{req.problem_id}" if req.student_id else f"public_{req.problem_id}"
    rng = get_stable_rng(seed)
    params = script.generate(rng)

    # 3. 验证
    if not hasattr(script, "check"):
        raise HTTPException(status_code=500, detail="Problem script missing check function")

    class SafeAnswers(dict):
        def get(self, key, default=None):
            val = super().get(key, default)
            # 处理 None、空字符串或只包含空白字符的字符串
            if val is None or str(val).strip() == "":
                return "0"
            return val

    try:
        results = script.check(params, SafeAnswers(req.answers))
    except Exception as e:
        # 容错：题目脚本在单字段提交或异常输入下抛错时，
        # 不让整个接口 500，而是将本次提交字段判为错误。
        print(f"WARN: check() failed for problem {req.problem_id}: {e}")
        submitted_keys = list(req.answers.keys()) if isinstance(req.answers, dict) else []
        results = {k: False for k in submitted_keys}
        
    # If guest, return verification results immediately without DB recording
    if not req.student_id:
        return {
            "correct": all(results.values()) if results else False,
            "results": results,
            "attempt_status": {}, # No persistence for guests
            "message": "Answer verified (Guest Mode)"
        }

    raw_meta = script.meta if hasattr(script, "meta") else {}
    meta = ensure_meta_inputs(raw_meta)
    meta_inputs = meta.get("inputs", {})
    
    # 修改逻辑：只处理用户本次提交了的 ID，并且去重
    # 这样可以支持单个填空的提交，而不会误伤其他未提交填空的尝试次数
    full_input_ids = get_problem_input_ids(req.problem_id, script)
    unique_full_input_ids = list(set(full_input_ids))
    submitted_input_ids = [k for k in unique_full_input_ids if k in req.answers]

    # 4. 记录尝试
    # require_student(session, req.student_id) # Already checked by Depend(get_current_student)

    # 只遍历用户提交了的 ID
    for input_id in submitted_input_ids:
        max_attempts = meta_inputs.get(input_id, {}).get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        answer = req.answers.get(input_id, "")

        attempt = session.exec(
            select(Attempt).where(
                Attempt.student_id == req.student_id,
                Attempt.problem_id == req.problem_id,
                Attempt.input_id == input_id,
            )
        ).first()

        # 如果已正确则跳过
        if attempt and attempt.correct:
            continue

        # 如果达到最大尝试次数则跳过
        attempts = attempt.attempts if attempt else 0
        if attempts >= max_attempts:
            continue

        attempts += 1
        is_correct = bool(results.get(input_id, False))

        if not attempt:
            attempt = Attempt(
                student_id=req.student_id,
                problem_id=req.problem_id,
                input_id=input_id,
            )
            session.add(attempt)

        attempt.attempts = attempts
        attempt.correct = is_correct
        attempt.last_answer = str(answer)
        attempt.updated_at = datetime.now(timezone.utc)

    session.commit()

    # 返回所有状态，以便前端更新显示
    attempt_status = build_attempt_status(
        session,
        req.student_id,
        req.problem_id,
        unique_full_input_ids,
        meta_inputs,
    )

    overall_correct = all(item["correct"] for item in attempt_status.values()) if attempt_status else False

    return {
        "correct": overall_correct,
        "results": results,
        "attempt_status": attempt_status,
        "message": "Answer checked",
    }

@router.get("/{problem_id}/{filename:path}")
def get_problem_resource(
    problem_id: str,
    filename: str,
    current_student: Optional[Student] = Depends(get_optional_current_student),
    session: Session = Depends(get_session)
):
    # 1. Access Check
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    student_id = current_student.student_id if current_student else None
    
    if state:
        if state.is_deleted:
             raise HTTPException(status_code=404, detail="Problem not found")
        if not state.is_visible:
             raise HTTPException(status_code=403, detail="Problem not published")
             
        # Guest Access Check
        if not student_id and not state.is_public_view:
             raise HTTPException(status_code=403, detail="Access denied")

    # 2. Safety Check
    if filename.endswith(".py") or filename.startswith(".") or "__pycache__" in filename:
        raise HTTPException(status_code=403, detail="Access denied to source files")

    file_path = os.path.join(PROBLEMS_DIR, problem_id, filename)
    
    # 3. Path Traversal Check
    try:
        abs_path = os.path.abspath(file_path)
        base_path = os.path.abspath(os.path.join(PROBLEMS_DIR, problem_id))
        if not abs_path.startswith(base_path):
            raise HTTPException(status_code=403, detail="Invalid path")
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid path")

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileResponse(file_path)

