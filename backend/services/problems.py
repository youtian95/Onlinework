# 本文件作用：提供问题相关的服务函数，包括加载问题脚本、构建尝试状态、获取问题内容和状态、获取问题排名等。


import os
import time
import importlib.util
from jinja2 import Template
from sqlmodel import Session, select
from datetime import datetime, timezone
from fastapi import HTTPException
from backend.utils import get_stable_rng
from backend.models import Student, Attempt, ProblemState

# 获取后端目录的绝对路径
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS_DIR = os.path.join(BACKEND_DIR, "problems")

# 简单的内存缓存: { problem_id: (timestamp, data) }
_RANKING_CACHE = {}
_CACHE_TTL = 10  # 缓存有效期 10 秒

DEFAULT_INPUT_SCORE = 1
DEFAULT_MAX_ATTEMPTS = 3

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
        
    # 4. 渲染模板
    input_helper = ProblemInputs()
    render_context = {**params, "input": input_helper}
    
    template = Template(content)
    rendered_content = template.render(**render_context)
    
    raw_meta = script.meta if hasattr(script, "meta") else {}
    meta = ensure_meta_inputs(raw_meta)
    meta_inputs = meta.get("inputs", {})
    attempt_status = build_attempt_status(
        session,
        student_id,
        problem_id,
        input_helper.inputs,
        meta_inputs,
    )

    return {
        "id": problem_id,
        "content": rendered_content,
        "input_ids": input_helper.inputs,
        "meta": meta,
        "attempt_status": attempt_status,
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
        if a.student_id not in student_stats:
            student_stats[a.student_id] = {
                "score": 0,
                "last_update": a.updated_at
            }
        
        if a.updated_at > student_stats[a.student_id]["last_update"]:
            student_stats[a.student_id]["last_update"] = a.updated_at
            
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

    ranking_list = []
    for sid, stats in student_stats.items():
        if sid not in student_map:
            continue
        ranking_list.append({
            "student_id": sid,
            "name": student_map.get(sid, "-"),
            "score": stats["score"],
            "last_update": stats["last_update"]
        })
        
    ranking_list.sort(key=lambda x: (-x["score"], x["last_update"]))
    
    for i, item in enumerate(ranking_list):
        item["rank"] = i + 1
        
    # 更新缓存
    _RANKING_CACHE[problem_id] = (now, ranking_list)
    
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
    total_possible_score = 0
    if os.path.exists(PROBLEMS_DIR):
        for name in os.listdir(PROBLEMS_DIR):
            # 过滤掉回收站或未发布的题目
            state = states_dict.get(name)
            is_visible = state.is_visible if state else False
            is_deleted = state.is_deleted if state else False

            if is_deleted or not is_visible:
                continue

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
                    total_possible_score += score

    # 3. 获取所有启用的学生 (排除测试账号和已删除账号)
    students = session.exec(select(Student).where(Student.enabled == True, Student.is_test == False, Student.is_deleted == False)).all()
    student_stats = {}
    student_map = {}
    
    for s in students:
        student_map[s.student_id] = s.name
        student_stats[s.student_id] = {
            "score": 0,
            "last_update": None 
        }

    # 4. 获取所有提交记录
    attempts = session.exec(select(Attempt)).all()
    
    for a in attempts:
        if a.student_id in student_stats:
            stats = student_stats[a.student_id]
            if stats["last_update"] is None or a.updated_at > stats["last_update"]:
                stats["last_update"] = a.updated_at
            if a.correct:
                if (a.problem_id, a.input_id) in problem_scores:
                    score = problem_scores[(a.problem_id, a.input_id)]
                    stats["score"] += score
            
    # 5. 生成排名列表
    ranking_list = []
    for sid, stats in student_stats.items():
        score = stats["score"]
        rate = 0
        if total_possible_score > 0:
            rate = round((score / total_possible_score) * 100, 1)
            
        ranking_list.append({
            "student_id": sid,
            "name": student_map.get(sid, "-"),
            "score": score,
            "score_rate": rate,
            "total_possible": total_possible_score,
            "last_update": stats["last_update"]
        })
        
    def sort_key(item):
        score = item["score"]
        dt = item["last_update"]
        if dt is None:
            dt = datetime.max.replace(tzinfo=timezone.utc)
        return (-score, dt)
        
    ranking_list.sort(key=sort_key)
    
    for i, item in enumerate(ranking_list):
        item["rank"] = i + 1
        
    # 更新缓存
    _RANKING_CACHE["TOTAL"] = (now, ranking_list)
    
    return ranking_list
