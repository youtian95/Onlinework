from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File
from fastapi.responses import FileResponse
from sqlmodel import Session, select, delete
from typing import Dict, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import re
import uuid
import shutil
from pathlib import Path

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
from backend.core.security import verify_token
from backend.core.config import PUBLIC_DIR
from backend.services.problems import (
    load_problem_script, 
    require_student, 
    get_problem_content_and_status, 
    get_problem_subproblem_bundle,
    PROBLEMS_DIR,
    build_attempt_status,
    get_problem_ranking,
    get_teamwork_personal_ranking,
    get_teamwork_team_ranking,
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


class JoinTeamRequest(BaseModel):
    team_no: int
    force_switch: bool = False


class ClaimSubproblemRequest(BaseModel):
    subproblem_no: int
    force_switch: bool = False

def get_session():
    with Session(engine) as session:
        yield session


def _get_teamwork_config(session: Session, problem_id: str) -> Optional[TeamWorkConfig]:
    return session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()


def _extract_teamwork_meta(problem_id: str) -> Optional[dict]:
    script = load_problem_script(problem_id)
    if not script or not hasattr(script, "meta"):
        return None

    raw_meta = script.meta
    if not isinstance(raw_meta, dict):
        return None

    teamwork = raw_meta.get("teamwork")
    if not isinstance(teamwork, dict):
        return None

    team_count = teamwork.get("team_count")
    team_size = teamwork.get("team_size")
    try:
        team_count = int(team_count)
        team_size = int(team_size)
    except (TypeError, ValueError):
        return None

    if team_count <= 0 or team_size <= 0:
        return None

    return {
        "team_count": team_count,
        "team_size": team_size,
        "subproblem_count": team_size,
    }


def _ensure_teamwork_config(session: Session, problem_id: str) -> Optional[TeamWorkConfig]:
    config = _get_teamwork_config(session, problem_id)
    meta_teamwork = _extract_teamwork_meta(problem_id)

    if not config and not meta_teamwork:
        return None

    changed = False

    if not config and meta_teamwork:
        config = TeamWorkConfig(
            problem_id=problem_id,
            team_count=meta_teamwork["team_count"],
            team_size=meta_teamwork["team_size"],
            subproblem_count=meta_teamwork["subproblem_count"],
        )
        session.add(config)
        session.flush()
        changed = True

    existing_team = session.exec(
        select(Team.id).where(Team.problem_id == problem_id)
    ).first()
    if config and existing_team is None:
        for team_no in range(1, config.team_count + 1):
            session.add(
                Team(
                    problem_id=problem_id,
                    team_no=team_no,
                    name=f"第{team_no}队",
                    max_members=config.team_size,
                )
            )
        changed = True

    if changed:
        session.commit()
        config = _get_teamwork_config(session, problem_id)

    return config


def _get_student_team_member(session: Session, problem_id: str, student_id: Optional[str]) -> Optional[TeamMember]:
    if not student_id:
        return None
    return session.exec(
        select(TeamMember).where(
            TeamMember.problem_id == problem_id,
            TeamMember.student_id == student_id,
        )
    ).first()


def _get_student_claim(session: Session, problem_id: str, team_id: int, student_id: str) -> Optional[TeamSubproblemClaim]:
    return session.exec(
        select(TeamSubproblemClaim).where(
            TeamSubproblemClaim.problem_id == problem_id,
            TeamSubproblemClaim.team_id == team_id,
            TeamSubproblemClaim.student_id == student_id,
        ).order_by(
            TeamSubproblemClaim.switch_count.desc(),
            TeamSubproblemClaim.claimed_at.desc(),
            TeamSubproblemClaim.id.desc(),
        )
    ).first()


def _normalize_team_claims(claims: list[TeamSubproblemClaim]) -> list[TeamSubproblemClaim]:
    """Keep at most one latest claim per student and one owner per subproblem."""
    if not claims:
        return []

    def _claim_sort_key(claim: TeamSubproblemClaim):
        claim_time = claim.claimed_at or datetime.min.replace(tzinfo=timezone.utc)
        return (claim_time, claim.id or 0)

    sorted_claims = sorted(claims, key=_claim_sort_key, reverse=True)
    used_students = set()
    used_subproblems = set()
    normalized = []

    for claim in sorted_claims:
        if claim.student_id in used_students:
            continue
        if claim.subproblem_no in used_subproblems:
            continue
        normalized.append(claim)
        used_students.add(claim.student_id)
        used_subproblems.add(claim.subproblem_no)

    return sorted(normalized, key=lambda item: item.subproblem_no)


def _build_teamwork_attempt_status(
    session: Session,
    problem_id: str,
    team_id: int,
    current_student_id: str,
    input_ids: list,
    meta_inputs: dict,
    input_sub_map: Dict[str, int],
):
    claims = session.exec(
        select(TeamSubproblemClaim).where(
            TeamSubproblemClaim.problem_id == problem_id,
            TeamSubproblemClaim.team_id == team_id,
        )
    ).all()
    claims = _normalize_team_claims(claims)
    owner_by_sub = {c.subproblem_no: c.student_id for c in claims}

    attempt_rows = session.exec(
        select(TeamAttempt).where(
            TeamAttempt.problem_id == problem_id,
            TeamAttempt.team_id == team_id,
        )
    ).all()
    attempt_map = {(a.student_id, a.input_id): a for a in attempt_rows}

    status = {}
    for input_id in set(input_ids or []):
        max_attempts = meta_inputs.get(input_id, {}).get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        sub_no = input_sub_map.get(input_id)
        owner_student_id = owner_by_sub.get(sub_no)

        attempts = 0
        correct = False
        last_answer = ""
        if owner_student_id:
            attempt = attempt_map.get((owner_student_id, input_id))
            if attempt:
                attempts = attempt.attempts
                correct = attempt.correct
                last_answer = attempt.last_answer

        remaining = 0 if correct else max(0, max_attempts - attempts)
        locked = (not correct) and attempts >= max_attempts

        status[input_id] = {
            "attempts": attempts,
            "remaining": remaining,
            "correct": correct,
            "locked": locked,
            "max_attempts": max_attempts,
            "last_answer": last_answer,
            "subproblem_no": sub_no,
            "owner_student_id": owner_student_id,
            "editable": bool(owner_student_id and owner_student_id == current_student_id),
        }

    return status, claims


def _clear_student_claim_records(session: Session, problem_id: str, student_id: str):
    old_submissions = session.exec(
        select(ProblemSubmission).where(
            ProblemSubmission.problem_id == problem_id,
            ProblemSubmission.student_id == student_id,
        )
    ).all()
    for sub in old_submissions:
        if sub.pdf_path:
            old_path = PUBLIC_DIR / sub.pdf_path
            if old_path.exists() and old_path.is_file():
                try:
                    old_path.unlink()
                except OSError:
                    pass

    session.exec(
        delete(ProblemSubmission).where(
            ProblemSubmission.problem_id == problem_id,
            ProblemSubmission.student_id == student_id,
        )
    )
    session.exec(
        delete(TeamSubmission).where(
            TeamSubmission.problem_id == problem_id,
            TeamSubmission.student_id == student_id,
        )
    )
    session.exec(
        delete(Attempt).where(
            Attempt.problem_id == problem_id,
            Attempt.student_id == student_id,
        )
    )
    session.exec(
        delete(TeamAttempt).where(
            TeamAttempt.problem_id == problem_id,
            TeamAttempt.student_id == student_id,
        )
    )


def _clear_student_teamwork_records(session: Session, problem_id: str, student_id: str):
    # Clear both new teamwork records and legacy personal records to avoid stale data after switching team.
    _clear_student_claim_records(session, problem_id, student_id)
    session.exec(
        delete(TeamSubproblemClaim).where(
            TeamSubproblemClaim.problem_id == problem_id,
            TeamSubproblemClaim.student_id == student_id,
        )
    )

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
    member_by_problem = {}
    if student_id:
        rows = session.exec(
            select(TeamMember).where(TeamMember.student_id == student_id)
        ).all()
        member_by_problem = {m.problem_id: m for m in rows}

    team_name_map = {}
    if member_by_problem:
        team_ids = [m.team_id for m in member_by_problem.values()]
        teams = session.exec(select(Team).where(Team.id.in_(team_ids))).all()
        team_name_map = {t.id: (t.team_no, t.name) for t in teams}

    # 预先获取该学生的所有尝试记录，减少数据库查询
    attempts_map = {}
    team_attempts_map = {}
    if student_id:
        student_attempts = session.exec(select(Attempt).where(Attempt.student_id == student_id)).all()
        for a in student_attempts:
            attempts_map[(a.problem_id, a.input_id)] = a
        student_team_attempts = session.exec(
            select(TeamAttempt).where(TeamAttempt.student_id == student_id)
        ).all()
        for a in student_team_attempts:
            team_attempts_map[(a.problem_id, a.input_id)] = a
        
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
            teamwork_config = _ensure_teamwork_config(session, name)
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
                    if teamwork_config:
                        attempt = team_attempts_map.get((name, input_id))
                    else:
                        attempt = attempts_map.get((name, input_id))
                    if attempt and attempt.correct:
                        obtained_score += s

            problems.append({
                "id": name,
                "title": script.meta.get("title", name),
                "total_score": total_score,
                "obtained_score": obtained_score,
                "is_terminated": is_terminated,
                "deadline": deadline,
                "teamwork_enabled": bool(teamwork_config),
                "team_joined": name in member_by_problem,
                "team_no": team_name_map.get(member_by_problem[name].team_id, (None, None))[0] if name in member_by_problem else None,
                "team_name": team_name_map.get(member_by_problem[name].team_id, (None, None))[1] if name in member_by_problem else None,
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
    teamwork_config = _ensure_teamwork_config(session, problem_id)
    team_member = None
    
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

    if teamwork_config and student_id:
        team_member = _get_student_team_member(session, problem_id, student_id)
        if not team_member:
            raise HTTPException(status_code=403, detail="Team selection required")
            
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

        if teamwork_config and student_id and team_member:
            input_ids = content.get("input_ids", [])
            raw_meta = content.get("meta", {}) if isinstance(content.get("meta"), dict) else {}
            meta = ensure_meta_inputs(raw_meta)
            meta_inputs = meta.get("inputs", {})
            input_sub_map = content.get("input_subproblem_map", {})

            subproblems = content.get("subproblems", [])
            if len(subproblems) != teamwork_config.subproblem_count:
                raise HTTPException(
                    status_code=500,
                    detail=f"Teamwork problem {problem_id} requires exactly {teamwork_config.subproblem_count} <subproblem> blocks in problem.md",
                )

            team_attempt_status, team_claims = _build_teamwork_attempt_status(
                session,
                problem_id,
                team_member.team_id,
                student_id,
                input_ids,
                meta_inputs,
                input_sub_map,
            )
            my_claim = _get_student_claim(session, problem_id, team_member.team_id, student_id)

            content["attempt_status"] = team_attempt_status
            content["input_subproblem_map"] = input_sub_map
            content["my_claim_subproblem"] = my_claim.subproblem_no if my_claim else None
            content["team_claims"] = [
                {
                    "student_id": c.student_id,
                    "subproblem_no": c.subproblem_no,
                    "claimed_at": c.claimed_at,
                }
                for c in sorted(team_claims, key=lambda x: x.subproblem_no)
            ]

        content["is_terminated"] = is_terminated
        content["deadline"] = deadline
        content["pdf_uploaded"] = bool(submission)
        content["pdf_filename"] = submission.original_filename if submission else None
        content["teamwork_enabled"] = bool(teamwork_config)
            
    return content


@router.get("/{problem_id}/team/me")
def get_my_team_info(
    problem_id: str,
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session),
):
    config = _ensure_teamwork_config(session, problem_id)
    if not config:
        return {
            "problem_id": problem_id,
            "teamwork_enabled": False,
            "joined": False,
            "team": None,
        }

    member = _get_student_team_member(session, problem_id, current_student.student_id)
    if not member:
        return {
            "problem_id": problem_id,
            "teamwork_enabled": True,
            "joined": False,
            "team": None,
        }

    team = session.exec(select(Team).where(Team.id == member.team_id)).first()
    return {
        "problem_id": problem_id,
        "teamwork_enabled": True,
        "joined": True,
        "team": {
            "team_id": team.id if team else member.team_id,
            "team_no": team.team_no if team else None,
            "team_name": team.name if team else None,
            "joined_at": member.joined_at,
        },
    }


@router.get("/{problem_id}/teams")
def get_problem_teams(
    problem_id: str,
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session),
):
    config = _ensure_teamwork_config(session, problem_id)
    if not config:
        raise HTTPException(status_code=404, detail="Teamwork is not enabled for this problem")

    teams = session.exec(
        select(Team).where(Team.problem_id == problem_id).order_by(Team.team_no)
    ).all()
    members = session.exec(
        select(TeamMember).where(TeamMember.problem_id == problem_id)
    ).all()

    student_ids = list({m.student_id for m in members})
    name_map = {}
    if student_ids:
        students = session.exec(select(Student).where(Student.student_id.in_(student_ids))).all()
        name_map = {s.student_id: s.name for s in students}

    members_by_team = {}
    for m in members:
        members_by_team.setdefault(m.team_id, []).append(m)

    rows = []
    for t in teams:
        team_members = members_by_team.get(t.id, [])
        rows.append({
            "team_id": t.id,
            "team_no": t.team_no,
            "name": t.name,
            "max_members": t.max_members,
            "member_count": len(team_members),
            "members": [
                {
                    "student_id": m.student_id,
                    "name": name_map.get(m.student_id, ""),
                    "joined_at": m.joined_at,
                }
                for m in sorted(team_members, key=lambda x: x.joined_at)
            ],
        })

    return {
        "problem_id": problem_id,
        "teamwork_enabled": True,
        "config": {
            "team_count": config.team_count,
            "team_size": config.team_size,
            "subproblem_count": config.subproblem_count,
        },
        "teams": rows,
    }


@router.post("/{problem_id}/team/join")
def join_team(
    problem_id: str,
    payload: JoinTeamRequest,
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session),
):
    config = _ensure_teamwork_config(session, problem_id)
    if not config:
        raise HTTPException(status_code=404, detail="Teamwork is not enabled for this problem")

    team = session.exec(
        select(Team).where(
            Team.problem_id == problem_id,
            Team.team_no == payload.team_no,
        )
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    existing = _get_student_team_member(session, problem_id, current_student.student_id)
    if existing and existing.team_id == team.id:
        return {
            "message": "Already in this team",
            "problem_id": problem_id,
            "team_no": team.team_no,
            "team_name": team.name,
            "switched": False,
            "data_cleared": False,
        }

    switched = bool(existing)
    if existing and not payload.force_switch:
        old_team = session.exec(select(Team).where(Team.id == existing.team_id)).first()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Switching team will clear previous submissions",
                "requires_confirmation": True,
                "current_team_no": old_team.team_no if old_team else None,
                "target_team_no": team.team_no,
            },
        )

    current_members = session.exec(
        select(TeamMember).where(
            TeamMember.problem_id == problem_id,
            TeamMember.team_id == team.id,
        )
    ).all()
    if len(current_members) >= team.max_members:
        raise HTTPException(status_code=409, detail="Team is full")

    data_cleared = False
    if existing:
        _clear_student_teamwork_records(session, problem_id, current_student.student_id)
        session.delete(existing)
        data_cleared = True

    new_member = TeamMember(
        problem_id=problem_id,
        team_id=team.id,
        student_id=current_student.student_id,
    )
    session.add(new_member)
    session.commit()

    return {
        "message": "Team joined",
        "problem_id": problem_id,
        "team_no": team.team_no,
        "team_name": team.name,
        "switched": switched,
        "data_cleared": data_cleared,
    }


@router.get("/{problem_id}/team/claim/me")
def get_my_claim_info(
    problem_id: str,
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session),
):
    config = _ensure_teamwork_config(session, problem_id)
    if not config:
        return {
            "problem_id": problem_id,
            "teamwork_enabled": False,
            "claimed": False,
            "subproblem_no": None,
        }

    member = _get_student_team_member(session, problem_id, current_student.student_id)
    if not member:
        raise HTTPException(status_code=403, detail="Team selection required")

    claim = _get_student_claim(session, problem_id, member.team_id, current_student.student_id)
    return {
        "problem_id": problem_id,
        "teamwork_enabled": True,
        "claimed": bool(claim),
        "subproblem_no": claim.subproblem_no if claim else None,
    }


@router.get("/{problem_id}/team/claims")
def get_team_claims(
    problem_id: str,
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session),
):
    config = _ensure_teamwork_config(session, problem_id)
    if not config:
        raise HTTPException(status_code=404, detail="Teamwork is not enabled for this problem")

    member = _get_student_team_member(session, problem_id, current_student.student_id)
    if not member:
        raise HTTPException(status_code=403, detail="Team selection required")

    claims = session.exec(
        select(TeamSubproblemClaim).where(
            TeamSubproblemClaim.problem_id == problem_id,
            TeamSubproblemClaim.team_id == member.team_id,
        )
    ).all()
    claims = _normalize_team_claims(claims)

    student_ids = list({c.student_id for c in claims})
    name_map = {}
    if student_ids:
        students = session.exec(select(Student).where(Student.student_id.in_(student_ids))).all()
        name_map = {s.student_id: s.name for s in students}

    return {
        "problem_id": problem_id,
        "team_id": member.team_id,
        "claims": [
            {
                "student_id": c.student_id,
                "name": name_map.get(c.student_id, ""),
                "subproblem_no": c.subproblem_no,
                "claimed_at": c.claimed_at,
            }
            for c in sorted(claims, key=lambda x: x.subproblem_no)
        ],
    }


@router.post("/{problem_id}/team/claim")
def claim_subproblem(
    problem_id: str,
    payload: ClaimSubproblemRequest,
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session),
):
    config = _ensure_teamwork_config(session, problem_id)
    if not config:
        raise HTTPException(status_code=404, detail="Teamwork is not enabled for this problem")

    member = _get_student_team_member(session, problem_id, current_student.student_id)
    if not member:
        raise HTTPException(status_code=403, detail="Team selection required")

    if payload.subproblem_no < 1 or payload.subproblem_no > config.subproblem_count:
        raise HTTPException(status_code=400, detail=f"subproblem_no must be in 1..{config.subproblem_count}")

    # 兼容历史脏数据：若同一学生在同一队伍下存在多条认领，保留最新一条并清理其余记录。
    own_claims = session.exec(
        select(TeamSubproblemClaim).where(
            TeamSubproblemClaim.problem_id == problem_id,
            TeamSubproblemClaim.team_id == member.team_id,
            TeamSubproblemClaim.student_id == current_student.student_id,
        ).order_by(
            TeamSubproblemClaim.switch_count.desc(),
            TeamSubproblemClaim.claimed_at.desc(),
            TeamSubproblemClaim.id.desc(),
        )
    ).all()
    existing = own_claims[0] if own_claims else None
    for stale_claim in own_claims[1:]:
        session.delete(stale_claim)
    if len(own_claims) > 1:
        session.flush()

    if existing and existing.subproblem_no == payload.subproblem_no:
        return {
            "message": "Already claimed",
            "problem_id": problem_id,
            "subproblem_no": existing.subproblem_no,
            "switched": False,
            "data_cleared": False,
        }

    occupied = session.exec(
        select(TeamSubproblemClaim).where(
            TeamSubproblemClaim.problem_id == problem_id,
            TeamSubproblemClaim.team_id == member.team_id,
            TeamSubproblemClaim.subproblem_no == payload.subproblem_no,
            TeamSubproblemClaim.student_id != current_student.student_id,
        )
    ).first()
    if occupied:
        raise HTTPException(status_code=409, detail="Subproblem already claimed by teammate")

    switched = bool(existing)
    if existing and (existing.switch_count or 0) >= 1:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Subproblem switch limit reached",
                "switch_limit": 1,
                "used_switches": existing.switch_count or 0,
            },
        )

    if existing and not payload.force_switch:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Switching subproblem will clear your previous submissions",
                "requires_confirmation": True,
                "current_subproblem_no": existing.subproblem_no,
                "target_subproblem_no": payload.subproblem_no,
            },
        )

    data_cleared = False
    if existing:
        _clear_student_claim_records(session, problem_id, current_student.student_id)
        existing.subproblem_no = payload.subproblem_no
        existing.switch_count = (existing.switch_count or 0) + 1
        existing.claimed_at = datetime.now(timezone.utc)
        data_cleared = True
    else:
        existing = TeamSubproblemClaim(
            problem_id=problem_id,
            team_id=member.team_id,
            student_id=current_student.student_id,
            subproblem_no=payload.subproblem_no,
            switch_count=0,
        )
        session.add(existing)

    session.commit()

    return {
        "message": "Subproblem claimed",
        "problem_id": problem_id,
        "subproblem_no": existing.subproblem_no,
        "switch_limit": 1,
        "used_switches": existing.switch_count or 0,
        "switched": switched,
        "data_cleared": data_cleared,
    }

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

    teamwork_config = _ensure_teamwork_config(session, problem_id)
    if teamwork_config:
        member = _get_student_team_member(session, problem_id, current_student.student_id)
        if not member:
            raise HTTPException(status_code=403, detail="Team selection required")

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
    scope: str = "personal",
    current_student: Student = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    teamwork_config = _ensure_teamwork_config(session, problem_id)
    if teamwork_config:
        scope_norm = (scope or "personal").strip().lower()
        if scope_norm in ("team", "group"):
            return get_teamwork_team_ranking(session, problem_id)
        return get_teamwork_personal_ranking(session, problem_id)

    return get_problem_ranking(session, problem_id)


def submit_answer(req: SubmitRequest, session: Session):
    teamwork_config = _ensure_teamwork_config(session, req.problem_id)
    member = None

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

    if teamwork_config:
        if not req.student_id:
            raise HTTPException(status_code=403, detail="Teamwork problem does not support guest submission")
        member = _get_student_team_member(session, req.problem_id, req.student_id)
        if not member:
            raise HTTPException(status_code=403, detail="Team selection required")

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

    if teamwork_config:
        claim = _get_student_claim(session, req.problem_id, member.team_id, req.student_id)
        if not claim:
            raise HTTPException(status_code=403, detail="Subproblem claim required")

        subproblem_bundle = get_problem_subproblem_bundle(req.problem_id, params)
        input_sub_map = subproblem_bundle.get("input_subproblem_map", {})
        if len(subproblem_bundle.get("subproblems", [])) != teamwork_config.subproblem_count:
            raise HTTPException(
                status_code=500,
                detail=f"Teamwork problem {req.problem_id} requires exactly {teamwork_config.subproblem_count} <subproblem> blocks in problem.md",
            )
        unauthorized_inputs = [
            input_id for input_id in submitted_input_ids
            if input_sub_map.get(input_id) != claim.subproblem_no
        ]
        if unauthorized_inputs:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "You can only modify inputs in your claimed subproblem",
                    "claimed_subproblem_no": claim.subproblem_no,
                    "unauthorized_inputs": unauthorized_inputs,
                },
            )

        for input_id in submitted_input_ids:
            max_attempts = meta_inputs.get(input_id, {}).get("max_attempts", DEFAULT_MAX_ATTEMPTS)
            answer = req.answers.get(input_id, "")

            attempt = session.exec(
                select(TeamAttempt).where(
                    TeamAttempt.student_id == req.student_id,
                    TeamAttempt.team_id == member.team_id,
                    TeamAttempt.problem_id == req.problem_id,
                    TeamAttempt.input_id == input_id,
                )
            ).first()

            if attempt and attempt.correct:
                continue

            attempts = attempt.attempts if attempt else 0
            if attempts >= max_attempts:
                continue

            attempts += 1
            is_correct = bool(results.get(input_id, False))

            if not attempt:
                attempt = TeamAttempt(
                    student_id=req.student_id,
                    team_id=member.team_id,
                    problem_id=req.problem_id,
                    input_id=input_id,
                )
                session.add(attempt)

            attempt.attempts = attempts
            attempt.correct = is_correct
            attempt.last_answer = str(answer)
            attempt.updated_at = datetime.now(timezone.utc)

        session.commit()

        attempt_status, _ = _build_teamwork_attempt_status(
            session,
            req.problem_id,
            member.team_id,
            req.student_id,
            unique_full_input_ids,
            meta_inputs,
            input_sub_map,
        )
        overall_correct = all(item["correct"] for item in attempt_status.values()) if attempt_status else False

        return {
            "correct": overall_correct,
            "results": results,
            "attempt_status": attempt_status,
            "message": "Answer checked (Teamwork)",
        }

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

