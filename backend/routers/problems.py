from fastapi import APIRouter, HTTPException, Depends, Header
from sqlmodel import Session, select
from typing import Dict, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import os

from backend.db import engine
from backend.models import Student, Attempt, ProblemState
from backend.utils import get_stable_rng
from backend.core.security import verify_token
from backend.services.problems import (
    load_problem_script, 
    require_student, 
    get_problem_content_and_status, 
    PROBLEMS_DIR,
    build_attempt_status,
    get_problem_ranking,
    get_total_ranking
)

router = APIRouter()

class SubmitRequest(BaseModel):
    # student_id optional/ignored in payload because we get it from token
    # But for compatibility, if frontend sends it, we might check consistency or ignore.
    student_id: Optional[str] = None 
    problem_id: str
    answers: Dict[str, str]

def get_session():
    with Session(engine) as session:
        yield session

def get_current_student(
    authorization: str = Header(None), 
    session: Session = Depends(get_session)
) -> Student:
    """Dependency to parse JWT and get current student"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    # Support "Bearer <token>"
    if authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    else:
        # Or just raw token
        token = authorization
        
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid Token")
        
    student_id = payload.get("sub")
    if not student_id:
        raise HTTPException(status_code=401, detail="Invalid Token Payload")
        
    student = session.exec(select(Student).where(Student.student_id == student_id)).first()
    if not student:
        raise HTTPException(status_code=401, detail="User not found")
        
    if not student.enabled:
        raise HTTPException(status_code=403, detail="Account disabled")
        
    return student


@router.get("")
def list_problems(
    current_student: Student = Depends(get_current_student), 
    session: Session = Depends(get_session)
):
    student_id = current_student.student_id
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
        
        # Default policy: Old problems (no state) are VISIBLE (True) to not break existing instances
        # But newly uploaded ones are defaults to invisible in my Admin logic.
        # Let's align: if no state record, treat as visible (legacy support).
        is_visible = state.is_visible if state else True
        is_deleted = state.is_deleted if state else False
        
        if is_deleted or not is_visible:
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
            meta_inputs = script.meta.get("inputs", {})
            total_score = 0
            obtained_score = 0
            
            for input_id, config in meta_inputs.items():
                s = config.get("score", 0)
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
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    student_id = current_student.student_id
    
    # Check access
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    if state:
        if state.is_deleted:
            raise HTTPException(status_code=404, detail="Problem not found")
        if not state.is_visible:
            raise HTTPException(status_code=403, detail="Problem not published")
            
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
        content["is_terminated"] = is_terminated
        content["deadline"] = deadline
            
    return content

@router.post("/submit")
# 注意：原始 API 是 /submit，而不是 /problems/submit。
# 为了保持路由模块的独立性，我们在这里定义，但在 main.py 中我们会单独处理挂载
# 以兼容前端直接请求 /submit 的情况
def submit_answer_endpoint(
    req: SubmitRequest, 
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    # Enforce student_id from token, ignoring whatever is in request body (for security)
    req.student_id = current_student.student_id
    return submit_answer(req, session)


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
        if state.deadline:
             if datetime.now(timezone.utc) > state.deadline.replace(tzinfo=timezone.utc):
                 raise HTTPException(status_code=400, detail="Submission deadline passed")

    # 1. 加载脚本
    script = load_problem_script(req.problem_id)
    if not script:
        raise HTTPException(status_code=404, detail="Problem not found")

    # 2. 重新生成参数
    rng = get_stable_rng(f"{req.student_id}_{req.problem_id}")
    params = script.generate(rng)

    # 3. 验证
    if not hasattr(script, "check"):
        raise HTTPException(status_code=500, detail="Problem script missing check function")

    try:
        results = script.check(params, req.answers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Check function error: {str(e)}")

    meta_inputs = script.meta.get("inputs", {}) if hasattr(script, "meta") else {}
    
    # 修改逻辑：只处理用户本次提交了的 ID
    # 这样可以支持单个填空的提交，而不会误伤其他未提交填空的尝试次数
    full_input_ids = list(meta_inputs.keys())
    submitted_input_ids = [k for k in full_input_ids if k in req.answers]

    # 4. 记录尝试
    # require_student(session, req.student_id) # Already checked by Depend(get_current_student)

    # 只遍历用户提交了的 ID
    for input_id in submitted_input_ids:
        max_attempts = meta_inputs.get(input_id, {}).get("max_attempts", 1)
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
        full_input_ids,
        meta_inputs,
    )

    overall_correct = all(item["correct"] for item in attempt_status.values()) if attempt_status else False

    return {
        "correct": overall_correct,
        "results": results,
        "attempt_status": attempt_status,
        "message": "Answer checked"
    }
