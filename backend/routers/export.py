from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Body
from fastapi.responses import Response, StreamingResponse, JSONResponse
from sqlmodel import Session, select, delete
from backend.db import engine
from backend.models import Student, Attempt, ProblemState
from backend.core.config import ARCHIVES_DIR
from backend.core.security import verify_token
from backend.services.problems import load_problem_script, PROBLEMS_DIR, get_stable_rng
from jinja2 import Template
import csv
import io
import zipfile
import markdown
import os
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel

# ReportLab imports for manual PDF construction
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
from bs4 import BeautifulSoup

from markdown_pdf import Section, MarkdownPdf

import logging
import tempfile
import shutil

router = APIRouter(prefix="/admin/export", tags=["export"])

def get_session():
    with Session(engine) as session:
        yield session

def verify_admin_token(token: str):
    if not token:
        raise HTTPException(status_code=401, detail="Missing Token")
    try:
        # 如果是 Bearer Token，去掉前缀
        clean_token = token.replace("Bearer ", "") if "Bearer " in token else token
        payload = verify_token(clean_token)
        if not payload or payload.get("role") != "admin":
            raise HTTPException(status_code=401, detail="Unauthorized")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Token")

class ArchiveCreateRequest(BaseModel):
    name: str

class ExportInputHelper:
    def __init__(self, attempts_map, meta_inputs):
        self.inputs = []
        self.attempts_map = attempts_map
        self.meta_inputs = meta_inputs
        self.total_possible = 0
        self.total_obtained = 0

    def __call__(self, input_id):
        self.inputs.append(input_id)
        attempt = self.attempts_map.get(input_id)
        
        config = self.meta_inputs.get(input_id, {})
        max_score = config.get("score", 0)
        self.total_possible += max_score
        
        user_score = 0
        ans_text = "____"
        is_correct = False
        
        if attempt:
            ans_text = attempt.last_answer if attempt.last_answer is not None else "____"
            if attempt.correct:
                user_score = max_score
                is_correct = True
        
        self.total_obtained += user_score
        
        color = "#67c23a" if is_correct else "#f56c6c"
        return f'<span style="color: {color}">**{ans_text}**</span> <sub>({user_score}/{max_score})</sub>'

# --- Helper Functions for Dump/Restore ---

def create_db_dump_bytes(session: Session) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        # 1. Students
        s_out = io.StringIO()
        s_writer = csv.writer(s_out)
        s_writer.writerow(["id", "student_id", "name", "enabled", "is_test", "is_deleted", "password_hash"]) # Header
        students = session.exec(select(Student)).all()
        for s in students:
            s_writer.writerow([s.id, s.student_id, s.name, s.enabled, s.is_test, s.is_deleted, s.password_hash])
        zip_file.writestr("students.csv", s_out.getvalue().encode("utf-8-sig"))
        
        # 2. Attempts
        a_out = io.StringIO()
        a_writer = csv.writer(a_out)
        a_writer.writerow(["id", "student_id", "problem_id", "input_id", "attempts", "correct", "last_answer", "updated_at"])
        attempts = session.exec(select(Attempt)).all()
        for a in attempts:
            a_writer.writerow([a.id, a.student_id, a.problem_id, a.input_id, a.attempts, a.correct, a.last_answer, a.updated_at.isoformat() if a.updated_at else ""])
        zip_file.writestr("attempts.csv", a_out.getvalue().encode("utf-8-sig"))
        
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def restore_db_from_bytes(content: bytes, session: Session):
    zip_buffer = io.BytesIO(content)
    try:
        with zipfile.ZipFile(zip_buffer, "r") as zf:
            names = zf.namelist()
            if "students.csv" not in names or "attempts.csv" not in names:
                raise ValueError("Missing CSV files in zip")
            
            # WIPE DATA
            session.exec(delete(Attempt))
            session.exec(delete(Student))
            
            session.commit()
            
            # Restore Students
            with zf.open("students.csv") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    def parse_bool(v): return str(v).lower() == 'true'
                    obj = Student(
                        student_id=row['student_id'],
                        name=row['name'],
                        enabled=parse_bool(row['enabled']),
                        is_test=parse_bool(row['is_test']),
                        is_deleted=parse_bool(row['is_deleted']),
                        password_hash=row['password_hash'] if row['password_hash'] else None
                    )
                    session.add(obj)
            
            # Restore Attempts
            with zf.open("attempts.csv") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    def parse_bool(v): return str(v).lower() == 'true'
                    obj = Attempt(
                        student_id=row['student_id'],
                        problem_id=row['problem_id'],
                        input_id=row['input_id'],
                        attempts=int(row['attempts']),
                        correct=parse_bool(row['correct']),
                        last_answer=row['last_answer'],
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.now()
                    )
                    session.add(obj)

            session.commit()
    except Exception as e:
        session.rollback()
        raise e

# --- Endpoints ---

@router.get("/db_dump")
def export_database(session: Session = Depends(get_session), token: str = Query(...)):
    verify_admin_token(token)
    zip_bytes = create_db_dump_bytes(session)
    response = Response(content=zip_bytes, media_type="application/zip")
    response.headers["Content-Disposition"] = f"attachment; filename=db_dump_{datetime.now().strftime('%Y%m%d')}.zip"
    return response

@router.post("/db_restore")
def import_database(
    file: UploadFile = File(...), 
    session: Session = Depends(get_session), 
    token: str = Query(...)
):
    verify_admin_token(token)
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files allowed")
    
    content = file.file.read()
    try:
        restore_db_from_bytes(content, session)
        return {"status": "success", "message": "Database restored"}
    except Exception as e:
        logging.error(f"Restore failed: {e}")
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

# --- Managed Archive Endpoints ---

@router.post("/archives")
def create_archive(
    data: ArchiveCreateRequest,
    session: Session = Depends(get_session), 
    token: str = Query(...)
):
    """
    1. Dump current DB to ZIP.
    2. Save to archives folder with name.
    3. Wipe students (except test) and attempts.
    """
    verify_admin_token(token)
    
    # Ensure Archives Directory
    if not os.path.exists(ARCHIVES_DIR):
        os.makedirs(ARCHIVES_DIR)
        
    # 1. Create Dump
    zip_bytes = create_db_dump_bytes(session)
    
    # 2. Save
    safe_name = "".join(c for c in data.name if c.isalnum() or c in (' ', '_', '-')).strip()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{safe_name}.zip"
    file_path = os.path.join(ARCHIVES_DIR, filename)
    
    with open(file_path, "wb") as f:
        f.write(zip_bytes)
        
    # 3. Wipe Active Data (Semester Reset Logic)
    try:
        session.exec(delete(Attempt))
        
        # Delete non-test students
        statement = delete(Student).where(Student.is_test == False)
        session.exec(statement)
        
        # Optional: Reset problem states or keep them? 
        # Usually for a new semester, problems might stay same, just students change.
        # So we keep ProblemStates (assignments).
        
        session.commit()
    except Exception as e:
        # If wipe fails, we still have the backup, but we should warn
        logging.error(f"Archive created but wipe failed: {e}")
        return JSONResponse(status_code=500, content={"status": "partial_error", "message": f"Archive saved as {filename}, but DB wipe failed: {str(e)}"})
    
    return {"status": "success", "message": f"Archived to {filename} and database cleared."}

@router.get("/archives")
def list_archives(token: str = Query(...)):
    verify_admin_token(token)
    if not os.path.exists(ARCHIVES_DIR):
        return []
    
    files = []
    for f in os.listdir(ARCHIVES_DIR):
        if f.endswith(".zip"):
            path = os.path.join(ARCHIVES_DIR, f)
            stat = os.stat(path)
            files.append({
                "filename": f,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    # Sort by new
    files.sort(key=lambda x: x["filename"], reverse=True)
    return files

@router.post("/archives/restore/{filename}")
def restore_archive(
    filename: str,
    session: Session = Depends(get_session),
    token: str = Query(...)
):
    verify_admin_token(token)
    
    file_path = os.path.join(ARCHIVES_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archive not found")
        
    with open(file_path, "rb") as f:
        content = f.read()
        
    try:
        restore_db_from_bytes(content, session)
        return {"status": "success", "message": f"Restored from {filename}"}
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

@router.delete("/archives/{filename}")
def delete_archive(
    filename: str,
    token: str = Query(...)
):
    verify_admin_token(token)
    
    file_path = os.path.join(ARCHIVES_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archive not found")
        
    try:
        os.remove(file_path)
        return {"status": "success", "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

# --- End New Endpoints ---

@router.get("/scores")
def export_scores(session: Session = Depends(get_session), token: str = Query(...)):
    verify_admin_token(token)
    
    students = session.exec(select(Student).where(Student.is_test == False, Student.is_deleted == False)).all()
    
    if not os.path.exists(PROBLEMS_DIR):
        problems = []
    else:
        published_ids = session.exec(select(ProblemState.problem_id).where(ProblemState.is_visible == True, ProblemState.is_deleted == False)).all()
        published_set = set(published_ids)
        problems = [f for f in os.listdir(PROBLEMS_DIR) if os.path.isdir(os.path.join(PROBLEMS_DIR, f)) and f in published_set]
        problems.sort()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    header = ["学号", "姓名", "总分"]
    prob_input_map = [] 
    prob_col_indices = {} 
    
    for pid in problems:
        script = load_problem_script(pid)
        p_title = pid
        inputs_meta = {}
        if script and hasattr(script, "meta"):
            p_title = script.meta.get("title", pid)
            inputs_meta = script.meta.get("inputs", {})
            
        header.append(f"{p_title}(总分)")
        prob_col_indices[pid] = len(header) - 1
        
        for iid, conf in inputs_meta.items():
            header.append(f"{p_title}-{iid}")
            prob_input_map.append((pid, iid, conf.get("score", 0)))
            
    writer.writerow(header)
    
    attempts = session.exec(select(Attempt)).all()
    att_map = {} 
    for a in attempts:
        att_map[(a.student_id, a.problem_id, a.input_id)] = a
        
    for s in students:
        row = [s.student_id, s.name, 0] 
        current_total = 0
        student_prob_scores = {pid: 0 for pid in problems}
        row_values = []
        
        for pid in problems:
            row_values.append(0) 
            idx_of_prob_total = len(row_values) - 1
            p_total = 0
            
            script = load_problem_script(pid)
            inputs_meta = script.meta.get("inputs", {}) if script and hasattr(script, "meta") else {}
            
            for iid, conf in inputs_meta.items():
                max_val = conf.get("score", 0)
                att = att_map.get((s.student_id, pid, iid))
                score = 0
                if att and att.correct:
                    score = max_val
                
                row_values.append(score)
                p_total += score
            
            row_values[idx_of_prob_total] = p_total
            student_prob_scores[pid] = p_total
            current_total += p_total
            
        row[2] = current_total
        row.extend(row_values)
        writer.writerow(row)
        
    output.seek(0)
    content_bytes = output.getvalue().encode("utf-8-sig")
    
    response = Response(content=content_bytes, media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=scores_{datetime.now().strftime('%Y%m%d')}.csv"
    response.headers["Content-Type"] = "text/csv; charset=utf-8-sig" 
    return response

@router.get("/work")
def export_work(session: Session = Depends(get_session), token: str = Query(...)):
    verify_admin_token(token)
    
    students = session.exec(select(Student).where(Student.is_test == False, Student.is_deleted == False)).all()
    
    if not os.path.exists(PROBLEMS_DIR):
        return Response("No problems found", status_code=404)
    
    published_ids = session.exec(select(ProblemState.problem_id).where(ProblemState.is_visible == True, ProblemState.is_deleted == False)).all()
    published_set = set(published_ids)
        
    problems = [f for f in os.listdir(PROBLEMS_DIR) if os.path.isdir(os.path.join(PROBLEMS_DIR, f)) and f in published_set]
    problems.sort()
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        all_attempts = session.exec(select(Attempt)).all()
        mega_map = {}
        for a in all_attempts:
            if a.student_id not in mega_map: mega_map[a.student_id] = {}
            if a.problem_id not in mega_map[a.student_id]: mega_map[a.student_id][a.problem_id] = {}
            mega_map[a.student_id][a.problem_id][a.input_id] = a
            
        for s in students:
            s_folder = f"{s.student_id}_{s.name}"
            pdf = MarkdownPdf(toc_level=2)
            student_has_work = False
            
            for pid in problems:
                script = load_problem_script(pid)
                if not script: continue
                
                rng = get_stable_rng(f"{s.student_id}_{pid}")
                try:
                    params = script.generate(rng)
                except:
                    params = {}
                
                md_path = os.path.join(PROBLEMS_DIR, pid, "problem.md")
                if not os.path.exists(md_path): continue
                
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                s_attempts = mega_map.get(s.student_id, {}).get(pid, {})
                meta_inputs = script.meta.get("inputs", {}) if hasattr(script, "meta") else {}
                
                helper = ExportInputHelper(s_attempts, meta_inputs)
                render_context = {**params, "input": helper}
                template = Template(content)
                filled_md = template.render(**render_context)
                
                summary = f"\n\n---\n**总得分: {helper.total_obtained} / {helper.total_possible}**"
                filled_md += summary
                final_md = f"# {pid}\n\n{filled_md}"
                
                zip_file.writestr(f"{s_folder}/{pid}.md", final_md)
                pdf.add_section(Section(final_md, toc=False))
                student_has_work = True
            
            if student_has_work:
                try:
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp_path = tmp.name
                    pass 
                    pdf.save(tmp_path)
                    with open(tmp_path, "rb") as f:
                        pdf_bytes = f.read()
                    zip_file.writestr(f"{s_folder}/{s.student_id}_{s.name}_全作业.pdf", pdf_bytes)
                except Exception as e:
                     print(f"PDF Render Error {s.student_id}: {e}")
                     zip_file.writestr(f"{s_folder}/pdf_error.txt", str(e))
                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except:
                            pass

    zip_buffer.seek(0)
    response = Response(content=zip_buffer.getvalue(), media_type="application/zip")
    response.headers["Content-Disposition"] = f"attachment; filename=student_work_{datetime.now().strftime('%Y%m%d')}.zip"
    return response
