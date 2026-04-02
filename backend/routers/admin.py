from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Header, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select, delete
from pydantic import BaseModel
from backend.db import engine
from backend.models import (
    Student,
    Attempt,
    ProblemState,
    ProblemSubmission,
    TeamWorkConfig,
    Team,
    TeamMember,
    TeamSubproblemClaim,
    TeamAttempt,
    TeamSubmission,
)
from backend.utils import get_stable_rng
from backend.services.problems import (
    load_problem_script,
    PROBLEMS_DIR,
    get_problem_content_and_status,
    get_problem_ranking,
    get_teamwork_personal_ranking,
    get_teamwork_team_ranking,
    get_total_ranking,
    ensure_meta_inputs,
    DEFAULT_MAX_ATTEMPTS,
    collect_input_ids,
    get_problem_input_ids
)
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


class TeamWorkConfigUpdate(BaseModel):
    team_count: Optional[int] = None
    team_size: Optional[int] = None

def get_session():
    with Session(engine) as session:
        yield session


def _verify_admin_token_value(token: Optional[str]):
    if not token:
        raise HTTPException(status_code=401, detail="Missing Token")

    payload = verify_token(token)
    if payload and payload.get("role") == "admin":
        return payload

    raise HTTPException(status_code=401, detail="Unauthorized")


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
    return _verify_admin_token_value(token)


def _extract_teamwork_meta(problem_id: str) -> dict:
    script = load_problem_script(problem_id)
    if not script or not hasattr(script, "meta"):
        return {}

    raw_meta = script.meta
    if not isinstance(raw_meta, dict):
        return {}

    teamwork = raw_meta.get("teamwork", {})
    if not isinstance(teamwork, dict):
        return {}

    return teamwork


def _resolve_teamwork_numbers(problem_id: str, payload: TeamWorkConfigUpdate) -> tuple[int, int]:
    teamwork_meta = _extract_teamwork_meta(problem_id)

    team_count = payload.team_count if payload.team_count is not None else teamwork_meta.get("team_count")
    team_size = payload.team_size if payload.team_size is not None else teamwork_meta.get("team_size")

    if team_count is None or team_size is None:
        raise HTTPException(
            status_code=400,
            detail="team_count/team_size missing: provide in request or script.meta.teamwork",
        )

    try:
        team_count = int(team_count)
        team_size = int(team_size)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="team_count/team_size must be integers")

    if team_count <= 0 or team_size <= 0:
        raise HTTPException(status_code=400, detail="team_count/team_size must be > 0")

    return team_count, team_size


def _has_teamwork_data(session: Session, problem_id: str) -> bool:
    if session.exec(select(TeamMember.id).where(TeamMember.problem_id == problem_id)).first() is not None:
        return True
    if session.exec(select(TeamSubproblemClaim.id).where(TeamSubproblemClaim.problem_id == problem_id)).first() is not None:
        return True
    if session.exec(select(TeamAttempt.id).where(TeamAttempt.problem_id == problem_id)).first() is not None:
        return True
    if session.exec(select(TeamSubmission.id).where(TeamSubmission.problem_id == problem_id)).first() is not None:
        return True
    return False


def _parse_positive_int(value, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")

    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{field_name} must be > 0")

    return parsed


def _sync_team_rows(session: Session, problem_id: str, team_count: int, team_size: int):
    existing_teams = session.exec(
        select(Team).where(Team.problem_id == problem_id).order_by(Team.team_no)
    ).all()
    teams_by_no = {team.team_no: team for team in existing_teams}

    removed_team_ids = [team.id for team in existing_teams if team.team_no > team_count and team.id is not None]
    if removed_team_ids:
        session.exec(
            delete(TeamSubmission).where(
                TeamSubmission.problem_id == problem_id,
                TeamSubmission.team_id.in_(removed_team_ids),
            )
        )
        session.exec(
            delete(TeamAttempt).where(
                TeamAttempt.problem_id == problem_id,
                TeamAttempt.team_id.in_(removed_team_ids),
            )
        )
        session.exec(
            delete(TeamSubproblemClaim).where(
                TeamSubproblemClaim.problem_id == problem_id,
                TeamSubproblemClaim.team_id.in_(removed_team_ids),
            )
        )
        session.exec(
            delete(TeamMember).where(
                TeamMember.problem_id == problem_id,
                TeamMember.team_id.in_(removed_team_ids),
            )
        )
        session.exec(delete(Team).where(Team.id.in_(removed_team_ids)))

    for team_no in range(1, team_count + 1):
        team = teams_by_no.get(team_no)
        if team:
            team.max_members = team_size
            if not team.name:
                team.name = f"第{team_no}队"
            continue

        session.add(
            Team(
                problem_id=problem_id,
                team_no=team_no,
                name=f"第{team_no}队",
                max_members=team_size,
            )
        )


def _save_teamwork_config(
    session: Session,
    problem_id: str,
    team_count: Optional[int],
    team_size: Optional[int],
):
    config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()

    if not config:
        if team_count is None or team_size is None:
            raise HTTPException(status_code=400, detail="team_count and team_size are required for teamwork upload")

        parsed_team_count = _parse_positive_int(team_count, "team_count")
        parsed_team_size = _parse_positive_int(team_size, "team_size")
        config = TeamWorkConfig(
            problem_id=problem_id,
            team_count=parsed_team_count,
            team_size=parsed_team_size,
            subproblem_count=parsed_team_size,
        )
        session.add(config)
        _sync_team_rows(session, problem_id, parsed_team_count, parsed_team_size)
        session.commit()
        session.refresh(config)
        return config, True

    parsed_team_count = config.team_count if team_count is None else _parse_positive_int(team_count, "team_count")
    parsed_team_size = config.team_size

    if team_size is not None:
        requested_team_size = _parse_positive_int(team_size, "team_size")
        if requested_team_size != config.team_size:
            raise HTTPException(status_code=400, detail="team_size cannot be changed after teamwork is created")

    config.team_count = parsed_team_count
    config.subproblem_count = config.team_size
    config.updated_at = datetime.now(timezone.utc)
    _sync_team_rows(session, problem_id, config.team_count, config.team_size)
    session.commit()
    session.refresh(config)
    return config, False


def _build_admin_team_attempt_status(
    session: Session,
    problem_id: str,
    team_id: int,
    input_ids: list,
    meta_inputs: dict,
    input_sub_map: dict,
):
    claims = session.exec(
        select(TeamSubproblemClaim)
        .where(
            TeamSubproblemClaim.problem_id == problem_id,
            TeamSubproblemClaim.team_id == team_id,
        )
        .order_by(TeamSubproblemClaim.claimed_at.desc(), TeamSubproblemClaim.id.desc())
    ).all()

    owner_by_subproblem = {}
    claimed_students = set()
    for claim in claims:
        if claim.student_id in claimed_students:
            continue
        if claim.subproblem_no in owner_by_subproblem:
            continue
        owner_by_subproblem[claim.subproblem_no] = claim.student_id
        claimed_students.add(claim.student_id)

    rows = session.exec(
        select(TeamAttempt)
        .where(TeamAttempt.problem_id == problem_id, TeamAttempt.team_id == team_id)
    ).all()

    attempt_map = {}
    for row in rows:
        attempt_map[(row.student_id, row.input_id)] = row

    status = {}
    for input_id in set(input_ids or []):
        config = meta_inputs.get(input_id, {}) if isinstance(meta_inputs, dict) else {}
        max_attempts = config.get("max_attempts", DEFAULT_MAX_ATTEMPTS)

        subproblem_no = input_sub_map.get(input_id)
        owner_student_id = owner_by_subproblem.get(subproblem_no)
        row = attempt_map.get((owner_student_id, input_id)) if owner_student_id else None
        attempts = row.attempts if row else 0
        correct = row.correct if row else False
        last_answer = row.last_answer if row and row.last_answer is not None else ""

        remaining = 0 if correct else max(0, max_attempts - attempts)
        locked = (not correct) and attempts >= max_attempts

        status[input_id] = {
            "attempts": attempts,
            "remaining": remaining,
            "correct": correct,
            "locked": locked,
            "max_attempts": max_attempts,
            "last_answer": last_answer,
            "owner_student_id": owner_student_id,
        }

    return status

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
    team_count: Optional[int] = Form(None),
    team_size: Optional[int] = Form(None),
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

    teamwork_meta = _extract_teamwork_meta(problem_id)

    # Update or create state
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    if not state:
        state = ProblemState(problem_id=problem_id, title=title, is_visible=False)
        session.add(state)
    else:
        state.title = title # Update title if changed
        # Keep existing visible/deadline/deleted states
        pass
    
    if teamwork_meta:
        _save_teamwork_config(session, problem_id, team_count, team_size)
    else:
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


@router.get('/teamwork/{problem_id}/config', dependencies=[Depends(verify_admin)])
def get_teamwork_config(problem_id: str, session: Session = Depends(get_session)):
    config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()

    meta_teamwork = _extract_teamwork_meta(problem_id)

    if not config:
        return {
            "problem_id": problem_id,
            "configured": False,
            "config": None,
            "meta_teamwork": meta_teamwork,
        }

    return {
        "problem_id": problem_id,
        "configured": True,
        "config": {
            "team_count": config.team_count,
            "team_size": config.team_size,
            "subproblem_count": config.subproblem_count,
            "updated_at": config.updated_at,
        },
        "meta_teamwork": meta_teamwork,
    }


@router.put('/teamwork/{problem_id}/config', dependencies=[Depends(verify_admin)])
def upsert_teamwork_config(
    problem_id: str,
    payload: TeamWorkConfigUpdate,
    session: Session = Depends(get_session),
):
    script = load_problem_script(problem_id)
    if not script:
        raise HTTPException(status_code=404, detail="Problem not found")

    config, created = _save_teamwork_config(session, problem_id, payload.team_count, payload.team_size)

    return {
        "message": "Teamwork config saved",
        "problem_id": problem_id,
        "team_count": config.team_count,
        "team_size": config.team_size,
        "subproblem_count": config.subproblem_count,
        "rule": created and "created with team_count/team_size" or "only team_count can be changed after creation",
    }


@router.post('/teamwork/{problem_id}/init', dependencies=[Depends(verify_admin)])
def init_teamwork_teams(
    problem_id: str,
    force_reset: bool = False,
    session: Session = Depends(get_session),
):
    config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()
    if not config:
        raise HTTPException(status_code=400, detail="Teamwork config not found")

    if _has_teamwork_data(session, problem_id) and not force_reset:
        raise HTTPException(
            status_code=409,
            detail="Teamwork data exists. Use force_reset=true to reinitialize and clear old data.",
        )

    # Reinitialize as an idempotent operation.
    session.exec(delete(TeamSubmission).where(TeamSubmission.problem_id == problem_id))
    session.exec(delete(TeamAttempt).where(TeamAttempt.problem_id == problem_id))
    session.exec(delete(TeamSubproblemClaim).where(TeamSubproblemClaim.problem_id == problem_id))
    session.exec(delete(TeamMember).where(TeamMember.problem_id == problem_id))
    session.exec(delete(Team).where(Team.problem_id == problem_id))

    created = []
    for no in range(1, config.team_count + 1):
        team = Team(
            problem_id=problem_id,
            team_no=no,
            name=f"第{no}队",
            max_members=config.team_size,
        )
        session.add(team)
        created.append({
            "team_no": no,
            "name": team.name,
            "max_members": team.max_members,
        })

    session.commit()

    return {
        "message": "Teams initialized",
        "problem_id": problem_id,
        "team_count": config.team_count,
        "team_size": config.team_size,
        "teams": created,
    }


@router.get('/teamwork/{problem_id}/overview', dependencies=[Depends(verify_admin)])
def get_teamwork_overview(problem_id: str, session: Session = Depends(get_session)):
    config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()
    teams = session.exec(
        select(Team).where(Team.problem_id == problem_id).order_by(Team.team_no)
    ).all()
    members = session.exec(
        select(TeamMember).where(TeamMember.problem_id == problem_id)
    ).all()
    claims = session.exec(
        select(TeamSubproblemClaim).where(TeamSubproblemClaim.problem_id == problem_id)
    ).all()

    student_ids = list({m.student_id for m in members})
    student_name_map = {}
    submission_map = {}
    if student_ids:
        students = session.exec(select(Student).where(Student.student_id.in_(student_ids))).all()
        student_name_map = {s.student_id: s.name for s in students}
        
        submissions = session.exec(select(ProblemSubmission).where(
            ProblemSubmission.problem_id == problem_id,
            ProblemSubmission.student_id.in_(student_ids)
        )).all()
        submission_map = {s.student_id: s.pdf_path for s in submissions}

    claims_map = {}
    for c in claims:
        claims_map[(c.team_id, c.student_id)] = c.subproblem_no

    members_by_team = {}
    for m in members:
        members_by_team.setdefault(m.team_id, []).append(m)

    team_items = []
    for t in teams:
        team_members = members_by_team.get(t.id, [])
        member_rows = []
        for m in team_members:
            member_rows.append({
                "student_id": m.student_id,
                "name": student_name_map.get(m.student_id, ""),
                "joined_at": m.joined_at,
                "claimed_subproblem": claims_map.get((t.id, m.student_id)),
                "pdf_path": submission_map.get(m.student_id)
            })

        team_items.append({
            "team_id": t.id,
            "team_no": t.team_no,
            "name": t.name,
            "max_members": t.max_members,
            "member_count": len(member_rows),
            "members": member_rows,
        })

    return {
        "problem_id": problem_id,
        "config": {
            "team_count": config.team_count,
            "team_size": config.team_size,
            "subproblem_count": config.subproblem_count,
        } if config else None,
        "teams": team_items,
    }


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
def get_student_progress_data(student_id: str, session: Session = Depends(get_session)):
    problems_data = []
    
    if not os.path.exists(PROBLEMS_DIR):
        return []

    # 1. 获取所有题目文件夹
    problem_folders = [f for f in os.listdir(PROBLEMS_DIR) if os.path.isdir(os.path.join(PROBLEMS_DIR, f))]
    
    # 2. 获取该学生的所有尝试记录
    attempts = session.exec(select(Attempt).where(Attempt.student_id == student_id)).all()
    # 转为字典映射: (problem_id, input_id) -> Attempt对象
    attempts_map = {(a.problem_id, a.input_id): a for a in attempts}

    team_attempts = session.exec(select(TeamAttempt).where(TeamAttempt.student_id == student_id)).all()
    team_attempts_map = {(a.problem_id, a.input_id): a for a in team_attempts}

    # 3. 获取该学生的所有PDF提交记录
    submissions = session.exec(select(ProblemSubmission).where(ProblemSubmission.student_id == student_id)).all()
    submission_map = {s.problem_id: s.pdf_path for s in submissions}

    teamwork_problem_ids = set(
        session.exec(
            select(TeamWorkConfig.problem_id).where(TeamWorkConfig.problem_id.in_(problem_folders))
        ).all()
    )

    # Filter out deleted problems
    deleted_ids = session.exec(select(ProblemState.problem_id).where(ProblemState.is_deleted == True)).all()
    deleted_set = set(deleted_ids)

    for problem_id in problem_folders:
        if problem_id in deleted_set:
            continue

        script = load_problem_script(problem_id)
        if not script:
            continue
            
        # Collect dynamic inputs via helper
        input_ids = get_problem_input_ids(problem_id, script)
        
        # Meta config inputs
        raw_meta = script.meta if hasattr(script, 'meta') else {}
        meta = ensure_meta_inputs(raw_meta)
        title = meta.get('title', problem_id)
        inputs_meta = meta.get('inputs', {})
        
        problem_inputs = {}
        is_teamwork_problem = problem_id in teamwork_problem_ids
        
        for input_id in input_ids:
            config = inputs_meta.get(input_id, {})
            max_attempts = config.get('max_attempts', DEFAULT_MAX_ATTEMPTS)
            
            # Recalculate from map
            arec = team_attempts_map.get((problem_id, input_id)) if is_teamwork_problem else attempts_map.get((problem_id, input_id))
            
            problem_inputs[input_id] = {
                'attempts': arec.attempts if arec else 0,
                'max_attempts': max_attempts,
                'correct': arec.correct if arec else False
            }
            
        problems_data.append({
            'id': problem_id,
            'title': title,
            'teamwork_enabled': is_teamwork_problem,
            'inputs': problem_inputs,
            'pdf_path': submission_map.get(problem_id)
        })
        
    return problems_data

@router.post('/attempts/update', dependencies=[Depends(verify_admin)])
def update_attempt(req: UpdateAttemptRequest, session: Session = Depends(get_session)):
    teamwork_config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == req.problem_id)
    ).first()

    if teamwork_config:
        member = session.exec(
            select(TeamMember).where(
                TeamMember.problem_id == req.problem_id,
                TeamMember.student_id == req.student_id,
            )
        ).first()
        if not member:
            raise HTTPException(status_code=404, detail='Team member not found for this student/problem')

        attempt = session.exec(
            select(TeamAttempt).where(
                TeamAttempt.student_id == req.student_id,
                TeamAttempt.problem_id == req.problem_id,
                TeamAttempt.team_id == member.team_id,
                TeamAttempt.input_id == req.input_id,
            )
        ).first()

        if not attempt:
            if req.attempts == 0 and not req.correct:
                return {'message': 'No change needed'}

            attempt = TeamAttempt(
                student_id=req.student_id,
                problem_id=req.problem_id,
                team_id=member.team_id,
                input_id=req.input_id,
                attempts=req.attempts,
                correct=req.correct,
            )
            session.add(attempt)
        else:
            attempt.attempts = req.attempts
            attempt.correct = req.correct

        session.commit()
        return {'message': 'Updated successfully'}

    # 普通题使用个人尝试记录
    attempt = session.exec(
        select(Attempt).where(
            Attempt.student_id == req.student_id,
            Attempt.problem_id == req.problem_id,
            Attempt.input_id == req.input_id
        )
    ).first()

    if not attempt:
        if req.attempts == 0 and not req.correct:
            return {'message': 'No change needed'}

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
def get_admin_ranking(problem_id: str, scope: str = "personal", session: Session = Depends(get_session)):
    teamwork_config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()
    if teamwork_config:
        scope_norm = (scope or "personal").strip().lower()
        if scope_norm in ("team", "group"):
            return get_teamwork_team_ranking(session, problem_id)
        return get_teamwork_personal_ranking(session, problem_id)

    return get_problem_ranking(session, problem_id)


@router.get('/problems/{problem_id}/content', dependencies=[Depends(verify_admin)])
def get_admin_problem_content(
    problem_id: str,
    student_id: Optional[str] = None,
    team_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    state = session.exec(select(ProblemState).where(ProblemState.problem_id == problem_id)).first()
    teamwork_config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()

    normalized_student_id = (student_id or "").strip() or None
    if normalized_student_id:
        student = session.exec(
            select(Student).where(
                Student.student_id == normalized_student_id,
                Student.is_deleted == False,
            )
        ).first()
        if not student:
            raise HTTPException(status_code=404, detail="Selected student not found")

    if team_id is not None and not teamwork_config:
        raise HTTPException(status_code=400, detail="This problem is not a teamwork problem")

    deadline = state.deadline if state else None
    if deadline and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    render_student_id = normalized_student_id if not teamwork_config else None
    content = get_problem_content_and_status(session, problem_id, render_student_id)

    if isinstance(content, dict):
        if teamwork_config:
            if team_id is not None:
                team = session.exec(
                    select(Team).where(Team.problem_id == problem_id, Team.id == team_id)
                ).first()
                if not team:
                    raise HTTPException(status_code=404, detail="Selected team not found")

                meta = content.get("meta", {}) if isinstance(content.get("meta"), dict) else {}
                meta_inputs = meta.get("inputs", {}) if isinstance(meta.get("inputs"), dict) else {}
                content["attempt_status"] = _build_admin_team_attempt_status(
                    session,
                    problem_id,
                    team_id,
                    content.get("input_ids", []),
                    meta_inputs,
                    content.get("input_subproblem_map", {}),
                )

            content["selected_team_id"] = team_id
            content["teamwork_enabled"] = True
        else:
            content["selected_student_id"] = normalized_student_id
            content["teamwork_enabled"] = False

        content['state'] = {
            'is_visible': bool(state.is_visible) if state else False,
            'is_deleted': bool(state.is_deleted) if state else False,
            'is_public_view': bool(state.is_public_view) if state else False,
            'deadline': deadline,
        }
    return content


@router.get('/problems/{problem_id}/files/{filename:path}')
def get_admin_problem_file(
    problem_id: str,
    filename: str,
    x_admin_token: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = None,
):
    auth_token = x_admin_token or token or authorization
    if auth_token and auth_token.startswith("Bearer "):
        auth_token = auth_token.split(" ", 1)[1]

    _verify_admin_token_value(auth_token)

    if filename.endswith(".py") or filename.startswith(".") or "__pycache__" in filename:
        raise HTTPException(status_code=403, detail="Access denied to source files")

    file_path = os.path.join(PROBLEMS_DIR, problem_id, filename)

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

@router.get('/ranking', dependencies=[Depends(verify_admin)])
def get_admin_total_ranking(session: Session = Depends(get_session)):
    return get_total_ranking(session)
