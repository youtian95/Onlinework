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

class ProblemInputs:
    def __init__(self):
        self.inputs = []

    def __call__(self, input_id):
        self.inputs.append(input_id)
        # 直接返回 HTML 占位符，不再依赖 KaTeX
        # 前端 marked 会保留此 HTML，onMounted 时会被替换
        return f'<span id="{input_id}" class="problem-input-placeholder" style="display:inline-block; min-width: 40px;"></span>'

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
    for input_id in input_ids:
        max_attempts = meta_inputs.get(input_id, {}).get("max_attempts", 1)
        # 查找尝试记录
        attempt = session.exec(
            select(Attempt).where(
                Attempt.student_id == student_id,
                Attempt.problem_id == problem_id,
                Attempt.input_id == input_id,
            )
        ).first()

        attempts = attempt.attempts if attempt else 0
        correct = attempt.correct if attempt else False
        remaining = 0 if correct else max(0, max_attempts - attempts)
        locked = (not correct) and attempts >= max_attempts

        status[input_id] = {
            "attempts": attempts,
            "remaining": remaining,
            "correct": correct,
            "locked": locked,
            "max_attempts": max_attempts,
        }
    return status

def get_problem_content_and_status(session: Session, problem_id: str, student_id: str):
    # 验证题目是否存在
    script = load_problem_script(problem_id)
    if not script:
        raise HTTPException(status_code=404, detail="Problem not found")

    require_student(session, student_id)
    
    # 1. 生成随机数生成器 (RNG)
    rng = get_stable_rng(f"{student_id}_{problem_id}")

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
    
    meta_inputs = script.meta.get("inputs", {}) if hasattr(script, "meta") else {}
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
        "meta": script.meta,
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
    
    meta_inputs = script.meta.get("inputs", {})
    
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
            score = input_conf.get("score", 0)
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
            is_visible = state.is_visible if state else True
            is_deleted = state.is_deleted if state else False

            if is_deleted or not is_visible:
                continue

            script = load_problem_script(name)
            if script and hasattr(script, "meta"):
                meta_inputs = script.meta.get("inputs", {})
                for input_id, config in meta_inputs.items():
                    score = config.get("score", 0)
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
                score = problem_scores.get((a.problem_id, a.input_id), 0)
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
