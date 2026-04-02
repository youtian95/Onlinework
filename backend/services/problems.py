# 本文件作用：提供问题相关的服务函数，包括加载问题脚本、构建尝试状态、获取问题内容和状态、获取问题排名等。


import os
import re
import time
import inspect
import importlib.util
from typing import Dict, Any
from jinja2 import Template
from sqlmodel import Session, select
from datetime import datetime, timezone
from fastapi import HTTPException
from backend.utils import get_stable_rng
from backend.services.problem_check_template import NumericCheckTemplate
from backend.models import (
    Student,
    Attempt,
    ProblemState,
    TeamWorkConfig,
    Team,
    TeamMember,
    TeamSubproblemClaim,
    TeamAttempt,
    ProblemSubmission,
)

# 获取后端目录的绝对路径
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS_DIR = os.path.join(BACKEND_DIR, "problems")

# 简单的内存缓存: { problem_id: (timestamp, data) }
_RANKING_CACHE = {}
_CACHE_TTL = 10  # 缓存有效期 10 秒

DEFAULT_INPUT_SCORE = 1
DEFAULT_MAX_ATTEMPTS = 3
SUBPROBLEM_BLOCK_RE = re.compile(
    r"^[ \t]*<subproblem(?:\s+title=(['\"])(.*?)\1)?\s*>[ \t]*(?:\r?\n)?"
    r"(.*?)"
    r"^[ \t]*</subproblem>[ \t]*$",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)


def _ensure_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def ensure_meta_inputs(meta):
    if not isinstance(meta, dict):
        return {"inputs": {}}
    if "inputs" not in meta or meta.get("inputs") is None:
        meta = dict(meta)
        meta["inputs"] = {}
    elif not isinstance(meta.get("inputs"), dict):
        meta = dict(meta)
        meta["inputs"] = {}
    return meta

class ProblemInputs:
    def __init__(self):
        self.inputs = []

    def __call__(self, input_id):
        self.inputs.append(input_id)
        # 生成标准的 HTML 占位符
        # 前端会查找 class="problem-input-placeholder" 的元素并进行替换
        # 使用 id 属性方便定位，虽然 HTML 规范不建议重复 ID，但在我们的替换逻辑中是兼容的
        return f'<span id="{input_id}" class="problem-input-placeholder" style="display:inline-block; min-width: 40px;"></span>'

def collect_input_ids(problem_id: str, params: dict) -> list:
    md_path = os.path.join(PROBLEMS_DIR, problem_id, "problem.md")
    if not os.path.exists(md_path):
        return []

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    input_helper = ProblemInputs()
    render_context = {**params, "input": input_helper}
    template = Template(content)
    # 虽然这里没有使用 render 的返回值，但必须执行 render 过程
    # 因为只有在渲染过程中才会执行 {{ input(...) }} 标签，
    # 从而触发 input_helper.__call__，把 input_id 收集到 input_helper.inputs 中
    template.render(**render_context)
    return list(set(input_helper.inputs))


def split_problem_markdown_by_subproblems(content: str):
    blocks = []
    plain_parts = []
    render_sequence = []
    last_end = 0

    for idx, match in enumerate(SUBPROBLEM_BLOCK_RE.finditer(content or ""), start=1):
        plain_chunk = content[last_end:match.start()]
        plain_parts.append(plain_chunk)
        if plain_chunk.strip():
            render_sequence.append({
                "type": "plain",
                "content": plain_chunk,
            })

        inner_markdown = (match.group(3) or "").strip("\n")
        title = match.group(2) or None
        blocks.append({
            "subproblem_no": idx,
            "title": title,
            "content": inner_markdown,
        })
        render_sequence.append({
            "type": "subproblem",
            "subproblem_no": idx,
            "title": title,
            "content": inner_markdown,
        })
        last_end = match.end()

    tail_chunk = content[last_end:]
    plain_parts.append(tail_chunk)
    if tail_chunk.strip():
        render_sequence.append({
            "type": "plain",
            "content": tail_chunk,
        })

    plain_content = "".join(plain_parts)
    return blocks, plain_content, render_sequence


def get_problem_subproblem_bundle(problem_id: str, params: dict):
    md_path = os.path.join(PROBLEMS_DIR, problem_id, "problem.md")
    if not os.path.exists(md_path):
        return {
            "plain_content": "",
            "input_subproblem_map": {},
            "subproblems": [],
            "render_sequence": [],
        }

    with open(md_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    blocks, plain_content, raw_sequence = split_problem_markdown_by_subproblems(raw_content)

    rendered_blocks = []
    rendered_plain_segments = []
    input_subproblem_map: Dict[str, int] = {}
    for block in blocks:
        helper = ProblemInputs()
        render_context = {**params, "input": helper}
        rendered_content = Template(block["content"]).render(**render_context)
        input_ids = list(dict.fromkeys(helper.inputs))
        for input_id in input_ids:
            input_subproblem_map[input_id] = block["subproblem_no"]

        rendered_blocks.append({
            "subproblem_no": block["subproblem_no"],
            "title": block["title"],
            "content": rendered_content,
            "input_ids": input_ids,
        })

    for seg in raw_sequence:
        if seg.get("type") != "plain":
            continue
        helper = ProblemInputs()
        render_context = {**params, "input": helper}
        rendered_plain = Template(seg.get("content") or "").render(**render_context)
        rendered_plain_segments.append({
            "type": "plain",
            "content": rendered_plain,
        })

    rendered_sequence = []
    plain_idx = 0
    for seg in raw_sequence:
        if seg.get("type") == "plain":
            rendered_sequence.append(rendered_plain_segments[plain_idx])
            plain_idx += 1
            continue
        if seg.get("type") == "subproblem":
            rendered_sequence.append({
                "type": "subproblem",
                "subproblem_no": seg.get("subproblem_no"),
            })

    return {
        "plain_content": plain_content,
        "input_subproblem_map": input_subproblem_map,
        "subproblems": rendered_blocks,
        "render_sequence": rendered_sequence,
    }

def get_problem_input_ids(problem_id: str, script=None) -> list:
    """Helper to collect all input ids for a problem dynamically regardless of meta config"""
    if not script:
        script = load_problem_script(problem_id)
        if not script:
            return []
            
    # Use fixed seed to ensure consistent generation for parameter-dependent inputs
    seed = f"public_{problem_id}"
    rng = get_stable_rng(seed)
    
    try:
        params = script.generate(rng) if hasattr(script, "generate") else {}
    except Exception:
        params = {}
        
    try:
        input_ids = collect_input_ids(problem_id, params)
        return list(set(input_ids))
    except Exception:
        return []

def load_problem_script(problem_id: str):
    script_path = os.path.join(PROBLEMS_DIR, problem_id, "script.py")
    if not os.path.exists(script_path):
        return None
    
    spec = importlib.util.spec_from_file_location("problem_script", script_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except FileNotFoundError:
        return None

    return module


def get_checker_classes(script_module):
    checker_classes = []
    if not script_module:
        return checker_classes

    for obj in script_module.__dict__.values():
        if not inspect.isclass(obj):
            continue
        if obj is NumericCheckTemplate:
            continue
        if getattr(obj, "__module__", None) != script_module.__name__:
            continue
        if issubclass(obj, NumericCheckTemplate):
            checker_classes.append(obj)

    checker_classes.sort(key=lambda cls: (getattr(cls, "order", 0), cls.__name__))
    return checker_classes


def run_checker_classes(script_module, params: Dict[str, Any], user_answers: Dict[str, Any]):
    checker_classes = get_checker_classes(script_module)
    if not checker_classes:
        raise ValueError("Problem script must define at least one class inheriting NumericCheckTemplate")

    merged_results: Dict[str, bool] = {}
    for checker_cls in checker_classes:
        if checker_cls.run is not NumericCheckTemplate.run:
            raise ValueError(
                f"Checker class {checker_cls.__name__} must use one method per input id and must not override run()"
            )
        checker = checker_cls(params, user_answers)
        run_method = getattr(checker, "run", None)
        if not callable(run_method):
            raise ValueError(f"Checker class {checker_cls.__name__} must define a run() method")
        result = run_method()
        if not isinstance(result, dict):
            raise ValueError(f"Checker class {checker_cls.__name__}.run() must return a dict")
        merged_results.update(result)

    return merged_results

def require_student(session: Session, student_id: str) -> Student:
    if not student_id:
         raise HTTPException(status_code=401, detail="Authentication required")
         
    student = session.exec(
        select(Student).where(Student.student_id == student_id)
    ).first()
    if not student or not student.enabled:
        raise HTTPException(status_code=403, detail="Student not allowed")
    return student

def build_attempt_status(
    session: Session,
    student_id: str,
    problem_id: str,
    input_ids: list,
    meta_inputs: dict,
):
    status = {}
    unique_input_ids = list(set(input_ids))
    for input_id in unique_input_ids:
        max_attempts = meta_inputs.get(input_id, {}).get("max_attempts", DEFAULT_MAX_ATTEMPTS)
        
        attempts = 0
        correct = False
        last_answer = ""
        
        # Only query DB if we have a student_id
        if student_id:
            attempt = session.exec(
                select(Attempt).where(
                    Attempt.student_id == student_id,
                    Attempt.problem_id == problem_id,
                    Attempt.input_id == input_id,
                )
            ).first()
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
        }
    return status

def get_problem_content_and_status(session: Session, problem_id: str, student_id: str = None):
    # 验证题目是否存在
    script = load_problem_script(problem_id)
    if not script:
        raise HTTPException(status_code=404, detail="Problem not found")

    if student_id:
        require_student(session, student_id)
    
    # 1. 生成随机数生成器 (RNG)
    if student_id:
        seed = f"{student_id}_{problem_id}"
    else:
        seed = f"public_{problem_id}" # Fixed seed for guests
        
    rng = get_stable_rng(seed)

    # 2. 从脚本生成参数
    params = script.generate(rng)
    
    # 3. 读取 Markdown 文件
    md_path = os.path.join(PROBLEMS_DIR, problem_id, "problem.md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="Problem markdown not found")
    
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    bundle = get_problem_subproblem_bundle(problem_id, params)

    # 4. 渲染模板
    input_helper = ProblemInputs()
    render_context = {**params, "input": input_helper}

    template = Template(bundle.get("plain_content") or content)
    rendered_content = template.render(**render_context)
    
    raw_meta = script.meta if hasattr(script, "meta") else {}
    meta = ensure_meta_inputs(raw_meta)
    meta_inputs = meta.get("inputs", {})
    attempt_status = build_attempt_status(
        session,
        student_id,
        problem_id,
        list(dict.fromkeys((input_helper.inputs or []) + list(bundle.get("input_subproblem_map", {}).keys()))),
        meta_inputs,
    )

    return {
        "id": problem_id,
        "content": rendered_content,
        "input_ids": list(dict.fromkeys((input_helper.inputs or []) + list(bundle.get("input_subproblem_map", {}).keys()))),
        "meta": meta,
        "attempt_status": attempt_status,
        "subproblems": bundle.get("subproblems", []),
        "input_subproblem_map": bundle.get("input_subproblem_map", {}),
        "render_sequence": bundle.get("render_sequence", []),
    }

# 获取题目排名
# 
# 返回格式:
#    [
#       {
#           "student_id": "stu01",
#           "score": 30,
#           "last_update": "2024-01-01T12:00:00Z",
#           "rank": 1
#       },
#       ...
#    ]
def get_problem_ranking(session: Session, problem_id: str):
    # 1. 检查缓存
    now = time.time()
    if problem_id in _RANKING_CACHE:
        ts, data = _RANKING_CACHE[problem_id]
        if now - ts < _CACHE_TTL:
            return data

    script = load_problem_script(problem_id)
    if not script or not hasattr(script, "meta"):
        return []
    
    meta = ensure_meta_inputs(script.meta)
    meta_inputs = meta.get("inputs", {})
    
    attempts = session.exec(
        select(Attempt).where(Attempt.problem_id == problem_id)
    ).all()
    
    student_stats = {}
    
    for a in attempts:
        current_update = _ensure_utc_datetime(a.updated_at)
        if a.student_id not in student_stats:
            student_stats[a.student_id] = {
                "score": 0,
                "last_update": current_update
            }
        
        if current_update is not None:
            last_update = student_stats[a.student_id]["last_update"]
            if last_update is None or current_update > last_update:
                student_stats[a.student_id]["last_update"] = current_update
            
        if a.correct:
            input_conf = meta_inputs.get(a.input_id, {})
            score = input_conf.get("score", DEFAULT_INPUT_SCORE)
            student_stats[a.student_id]["score"] += score
            
    # Fetch student names
    student_ids = list(student_stats.keys())
    students = session.exec(select(Student).where(
        Student.student_id.in_(student_ids),
        Student.is_test == False,
        Student.is_deleted == False
    )).all()
    student_map = {s.student_id: s.name for s in students}

    # Fetch submissions
    submissions = session.exec(select(ProblemSubmission).where(
        ProblemSubmission.problem_id == problem_id,
        ProblemSubmission.student_id.in_(student_ids)
    )).all()
    submission_map = {s.student_id: s.pdf_path for s in submissions}

    ranking_list = []
    for sid, stats in student_stats.items():
        if sid not in student_map:
            continue
        ranking_list.append({
            "student_id": sid,
            "name": student_map.get(sid, "-"),
            "score": stats["score"],
            "last_update": stats["last_update"],
            "pdf_path": submission_map.get(sid)
        })
        
    def sort_key(item):
        dt = _ensure_utc_datetime(item["last_update"])
        if dt is None:
            dt = datetime.max.replace(tzinfo=timezone.utc)
        return (-item["score"], dt)

    ranking_list.sort(key=sort_key)
    
    for i, item in enumerate(ranking_list):
        item["rank"] = i + 1
        
    # 更新缓存
    _RANKING_CACHE[problem_id] = (now, ranking_list)
    
    return ranking_list
def _build_input_subproblem_map(problem_id: str, params: dict, subproblem_count: int) -> Dict[str, int]:
    bundle = get_problem_subproblem_bundle(problem_id, params)
    mapping = bundle.get("input_subproblem_map", {})
    if len(bundle.get("subproblems", [])) != subproblem_count:
        raise HTTPException(
            status_code=500,
            detail=f"Teamwork problem {problem_id} requires exactly {subproblem_count} <subproblem> blocks in problem.md",
        )
    if not mapping:
        raise HTTPException(
            status_code=500,
            detail=f"Teamwork problem {problem_id} has no inputs inside <subproblem> blocks",
        )
    return mapping


def _get_input_score_map(problem_id: str, script) -> tuple[list, dict, int]:
    input_ids = get_problem_input_ids(problem_id, script)
    meta = ensure_meta_inputs(script.meta) if script and hasattr(script, "meta") else {"inputs": {}}
    meta_inputs = meta.get("inputs", {})

    input_scores = {}
    total_possible = 0
    for input_id in set(input_ids):
        score = meta_inputs.get(input_id, {}).get("score", DEFAULT_INPUT_SCORE)
        input_scores[input_id] = score
        total_possible += score

    return input_ids, input_scores, total_possible


def get_teamwork_personal_ranking(session: Session, problem_id: str):
    cache_key = f"TW_PERSONAL:{problem_id}"
    now = time.time()
    if cache_key in _RANKING_CACHE:
        ts, data = _RANKING_CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()
    if not config:
        return []

    script = load_problem_script(problem_id)
    if not script:
        return []

    input_ids, input_scores, _ = _get_input_score_map(problem_id, script)
    rng = get_stable_rng(f"public_{problem_id}")
    try:
        params = script.generate(rng) if hasattr(script, "generate") else {}
    except Exception:
        params = {}
    input_sub_map = _build_input_subproblem_map(problem_id, params, config.subproblem_count)

    subproblem_total = {}
    for input_id, score in input_scores.items():
        sub_no = input_sub_map.get(input_id)
        if sub_no is None:
            continue
        subproblem_total[sub_no] = subproblem_total.get(sub_no, 0) + score

    members = session.exec(
        select(TeamMember).where(TeamMember.problem_id == problem_id)
    ).all()
    if not members:
        return []

    member_by_student = {m.student_id: m for m in members}
    student_ids = list(member_by_student.keys())

    students = session.exec(select(Student).where(
        Student.student_id.in_(student_ids),
        Student.enabled == True,
        Student.is_test == False,
        Student.is_deleted == False,
    )).all()
    student_name_map = {s.student_id: s.name for s in students}
    valid_student_ids = set(student_name_map.keys())

    team_ids = list({m.team_id for m in members})
    team_rows = session.exec(select(Team).where(Team.id.in_(team_ids))).all()
    team_map = {t.id: t for t in team_rows}

    claims = session.exec(
        select(TeamSubproblemClaim).where(TeamSubproblemClaim.problem_id == problem_id)
    ).all()
    claim_by_student = {c.student_id: c.subproblem_no for c in claims}

    attempts = session.exec(
        select(TeamAttempt).where(TeamAttempt.problem_id == problem_id)
    ).all()

    stats = {
        sid: {"score": 0, "last_update": None}
        for sid in valid_student_ids
    }

    for a in attempts:
        sid = a.student_id
        if sid not in stats:
            continue

        current_update = _ensure_utc_datetime(a.updated_at)
        current_last = stats[sid]["last_update"]
        if current_update is not None and (current_last is None or current_update > current_last):
            stats[sid]["last_update"] = current_update

        if not a.correct:
            continue

        expected_sub = claim_by_student.get(sid)
        if expected_sub is None:
            continue
        if input_sub_map.get(a.input_id) != expected_sub:
            continue

        stats[sid]["score"] += input_scores.get(a.input_id, DEFAULT_INPUT_SCORE)

    ranking_list = []
    submissions = session.exec(select(ProblemSubmission).where(
        ProblemSubmission.problem_id == problem_id
    )).all()
    submission_map = {s.student_id: s.pdf_path for s in submissions}

    for sid in valid_student_ids:
        member = member_by_student.get(sid)
        if not member:
            continue

        claimed_sub = claim_by_student.get(sid)
        total_possible = subproblem_total.get(claimed_sub, 0)
        score = stats[sid]["score"]
        score_rate = round((score / total_possible) * 100, 1) if total_possible > 0 else 0

        team = team_map.get(member.team_id)
        ranking_list.append({
            "student_id": sid,
            "name": student_name_map.get(sid, "-"),
            "team_id": member.team_id,
            "team_no": team.team_no if team else None,
            "subproblem_no": claimed_sub,
            "score": score,
            "total_possible": total_possible,
            "score_rate": score_rate,
            "last_update": stats[sid]["last_update"],
            "pdf_path": submission_map.get(sid)
        })

    def sort_key(item):
        dt = _ensure_utc_datetime(item["last_update"])
        if dt is None:
            dt = datetime.max.replace(tzinfo=timezone.utc)
        return (-item["score_rate"], -item["score"], dt)

    ranking_list.sort(key=sort_key)
    for i, item in enumerate(ranking_list):
        item["rank"] = i + 1

    _RANKING_CACHE[cache_key] = (now, ranking_list)
    return ranking_list


def get_teamwork_team_ranking(session: Session, problem_id: str):
    cache_key = f"TW_TEAM:{problem_id}"
    now = time.time()
    if cache_key in _RANKING_CACHE:
        ts, data = _RANKING_CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    config = session.exec(
        select(TeamWorkConfig).where(TeamWorkConfig.problem_id == problem_id)
    ).first()
    if not config:
        return []

    script = load_problem_script(problem_id)
    if not script:
        return []

    _, input_scores, total_possible = _get_input_score_map(problem_id, script)

    teams = session.exec(
        select(Team).where(Team.problem_id == problem_id).order_by(Team.team_no)
    ).all()
    if not teams:
        return []

    members = session.exec(
        select(TeamMember).where(TeamMember.problem_id == problem_id)
    ).all()
    member_count_map = {}
    for m in members:
        member_count_map[m.team_id] = member_count_map.get(m.team_id, 0) + 1

    attempts = session.exec(
        select(TeamAttempt).where(TeamAttempt.problem_id == problem_id)
    ).all()

    stats = {
        t.id: {"score": 0, "last_update": None, "counted_inputs": set()}
        for t in teams
    }

    for a in attempts:
        if a.team_id not in stats:
            continue

        current_update = _ensure_utc_datetime(a.updated_at)
        current_last = stats[a.team_id]["last_update"]
        if current_update is not None and (current_last is None or current_update > current_last):
            stats[a.team_id]["last_update"] = current_update

        if not a.correct:
            continue
        if a.input_id not in input_scores:
            continue

        if a.input_id in stats[a.team_id]["counted_inputs"]:
            continue
        stats[a.team_id]["counted_inputs"].add(a.input_id)
        stats[a.team_id]["score"] += input_scores.get(a.input_id, DEFAULT_INPUT_SCORE)

    ranking_list = []
    for t in teams:
        score = stats[t.id]["score"]
        score_rate = round((score / total_possible) * 100, 1) if total_possible > 0 else 0
        ranking_list.append({
            "team_id": t.id,
            "team_no": t.team_no,
            "team_name": t.name,
            "member_count": member_count_map.get(t.id, 0),
            "score": score,
            "total_possible": total_possible,
            "score_rate": score_rate,
            "last_update": stats[t.id]["last_update"],
        })

    def sort_key(item):
        dt = _ensure_utc_datetime(item["last_update"])
        if dt is None:
            dt = datetime.max.replace(tzinfo=timezone.utc)
        return (-item["score_rate"], -item["score"], dt)

    ranking_list.sort(key=sort_key)
    for i, item in enumerate(ranking_list):
        item["rank"] = i + 1

    _RANKING_CACHE[cache_key] = (now, ranking_list)
    return ranking_list

def get_total_ranking(session: Session):
    # 1. 检查缓存
    now = time.time()
    if "TOTAL" in _RANKING_CACHE:
        ts, data = _RANKING_CACHE["TOTAL"]
        if now - ts < _CACHE_TTL:
            return data

    # 2. 加载所有题目分值配置
    # 获取题目状态以排除回收站和不可见题目
    all_states = session.exec(select(ProblemState)).all()
    states_dict = {s.problem_id: s for s in all_states}

    problem_scores = {} # { (problem_id, input_id): score }
    visible_problem_ids = set()
    if os.path.exists(PROBLEMS_DIR):
        for name in os.listdir(PROBLEMS_DIR):
            # 过滤掉回收站或未发布的题目
            state = states_dict.get(name)
            is_visible = state.is_visible if state else False
            is_deleted = state.is_deleted if state else False

            if is_deleted or not is_visible:
                continue

            visible_problem_ids.add(name)

            script = load_problem_script(name)
            if script:
                # Use helper to find all input IDs
                input_ids = get_problem_input_ids(name, script)
                
                meta = ensure_meta_inputs(script.meta) if hasattr(script, "meta") else {"inputs": {}}
                meta_inputs = meta.get("inputs", {})
                
                for input_id in input_ids:
                    config = meta_inputs.get(input_id, {})
                    score = config.get("score", DEFAULT_INPUT_SCORE)
                    problem_scores[(name, input_id)] = score

    # 区分普通题和团队题，团队题需要特殊处理分母和得分统计
    non_team_problem_ids = set(visible_problem_ids) # 普通题
    teamwork_problem_ids = set()
    teamwork_configs = {} # { problem_id: TeamWorkConfig }
    if visible_problem_ids:
        team_problem_rows = session.exec(
            select(TeamWorkConfig).where(TeamWorkConfig.problem_id.in_(list(visible_problem_ids)))
        ).all()
        teamwork_problem_ids = {row.problem_id for row in team_problem_rows}
        teamwork_configs = {row.problem_id: row for row in team_problem_rows}
        non_team_problem_ids = visible_problem_ids - teamwork_problem_ids

    # 总分母分为普通题基础分，和每个学生不同团队题认领分
    base_total_possible = sum(
        score
        for (pid, _), score in problem_scores.items()
        if pid in non_team_problem_ids
    )

    # 团队题计分时仍按认领子题过滤，需要构建 input -> 子题映射
    teamwork_input_sub_map = {} # { problem_id: { input_id: subproblem_no } }
    for problem_id in teamwork_problem_ids:
        script = load_problem_script(problem_id)
        if not script:
            teamwork_input_sub_map[problem_id] = {}
            continue

        rng = get_stable_rng(f"public_{problem_id}")
        try:
            params = script.generate(rng) if hasattr(script, "generate") else {}
        except Exception:
            params = {}

        config = teamwork_configs.get(problem_id)
        if not config:
            teamwork_input_sub_map[problem_id] = {}
            continue

        input_sub_map = _build_input_subproblem_map(problem_id, params, config.subproblem_count)
        teamwork_input_sub_map[problem_id] = input_sub_map

    # 3. 获取所有启用的学生 (排除测试账号和已删除账号)
    students = session.exec(select(Student).where(Student.enabled == True, Student.is_test == False, Student.is_deleted == False)).all()
    student_stats = {}
    student_map = {}
    
    for s in students:
        student_map[s.student_id] = s.name
        student_stats[s.student_id] = {
            "score": 0,
            "last_update": None,
            "total_possible": base_total_possible,
        }

    # 团队题分母按认领限制；同时用于团队题得分过滤时读取认领关系
    if teamwork_problem_ids and student_stats:
        claims = session.exec(
            select(TeamSubproblemClaim).where(
                TeamSubproblemClaim.problem_id.in_(list(teamwork_problem_ids)),
                TeamSubproblemClaim.student_id.in_(list(student_stats.keys())),
            )
        ).all()
        claim_map = {
            (claim.problem_id, claim.student_id): claim.subproblem_no
            for claim in claims
        }
        # 为每个认领了题目的学生增加对应的总分母
        for claim in claims:
            input_sub_map = teamwork_input_sub_map.get(claim.problem_id, {})
            # 此学生在此题目中认领的子题号是 claim.subproblem_no
            # 找到对应此子题号的所有输入框，并累加分数
            for input_id, sub_no in input_sub_map.items():
                if sub_no == claim.subproblem_no:
                    score = problem_scores.get((claim.problem_id, input_id), 0)
                    student_stats[claim.student_id]["total_possible"] += score
    else:
        claim_map = {}

    # 4. 获取并统计普通题提交记录
    attempts = []
    if non_team_problem_ids:
        attempts = session.exec(
            select(Attempt).where(Attempt.problem_id.in_(list(non_team_problem_ids)))
        ).all()

    for a in attempts:
        if a.student_id in student_stats:
            stats = student_stats[a.student_id]
            current_update = _ensure_utc_datetime(a.updated_at)
            if current_update is not None and (stats["last_update"] is None or current_update > stats["last_update"]):
                stats["last_update"] = current_update
            if a.correct:
                if (a.problem_id, a.input_id) in problem_scores:
                    score = problem_scores[(a.problem_id, a.input_id)]
                    stats["score"] += score

    # 4.1 统计团队题提交记录
    team_attempts = []
    if teamwork_problem_ids:
        team_attempts = session.exec(
            select(TeamAttempt).where(TeamAttempt.problem_id.in_(list(teamwork_problem_ids)))
        ).all()

    for a in team_attempts:
        if a.student_id in student_stats:
            stats = student_stats[a.student_id]
            current_update = _ensure_utc_datetime(a.updated_at)
            if current_update is not None and (stats["last_update"] is None or current_update > stats["last_update"]):
                stats["last_update"] = current_update
            if a.correct:
                claimed_sub = claim_map.get((a.problem_id, a.student_id))
                if claimed_sub is None:
                    continue
                input_sub_map = teamwork_input_sub_map.get(a.problem_id, {})
                if input_sub_map.get(a.input_id) != claimed_sub:
                    continue
                if (a.problem_id, a.input_id) in problem_scores:
                    score = problem_scores[(a.problem_id, a.input_id)]
                    stats["score"] += score
            
    # 5. 生成排名列表
    ranking_list = []
    for sid, stats in student_stats.items():
        score = stats["score"]
        rate = 0
        total_possible = stats["total_possible"]
        if total_possible > 0:
            rate = round((score / total_possible) * 100, 1)
            
        ranking_list.append({
            "student_id": sid,
            "name": student_map.get(sid, "-"),
            "score": score,
            "score_rate": rate,
            "total_possible": total_possible,
            "last_update": stats["last_update"]
        })
        
    def sort_key(item):
        rate = item["score_rate"]
        score = item["score"]
        dt = _ensure_utc_datetime(item["last_update"])
        if dt is None:
            dt = datetime.max.replace(tzinfo=timezone.utc)
        return (-rate, -score, dt)
        
    ranking_list.sort(key=sort_key)
    
    for i, item in enumerate(ranking_list):
        item["rank"] = i + 1
        
    # 更新缓存
    _RANKING_CACHE["TOTAL"] = (now, ranking_list)
    
    return ranking_list
