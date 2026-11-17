# 分组文字作业服务：识别题目模式、读取及保存各组员独立报告，不调用判题器或计分。
# 使用流程：题目元数据声明 submission_mode="team_text"，接口校验组员认领后调用本模块。
# 输入为题目元数据、数据库会话及报告内容；输出为提交记录字典，版本冲突返回 HTTP 409。
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.models import TeamTextSubmission


def is_team_text_meta(meta: dict) -> bool:
    """判断是否为分组文字作业；meta 为题目脚本的元数据字典。"""
    return isinstance(meta, dict) and meta.get("submission_mode") == "team_text"


def get_team_text_submission(session: Session, problem_id: str, team_id: int | None, student_id: str | None) -> dict:
    """读取个人报告；session 为会话，problem_id 为题号，team_id 为小组，student_id 为认领者或空预览。"""
    row = session.exec(select(TeamTextSubmission).where(TeamTextSubmission.problem_id == problem_id, TeamTextSubmission.team_id == team_id, TeamTextSubmission.student_id == student_id)).first() if team_id is not None and student_id else None
    return _serialize_report(row)


def _serialize_report(row: TeamTextSubmission | None) -> dict:
    """将报告转换为接口数据；row 为数据库记录，无记录时返回空报告。"""
    return {"content": row.content if row else "", "revision": row.revision if row else 0, "student_id": row.student_id if row else None, "subproblem_no": row.subproblem_no if row else None, "updated_at": row.updated_at if row else None}


def get_team_text_submissions(session: Session, problem_id: str, team_id: int | None) -> list[dict]:
    """读取本组所有独立报告供只读查看；session 为会话，problem_id 为题号，team_id 为小组或空预览。"""
    if team_id is None:
        return []
    rows = session.exec(select(TeamTextSubmission).where(TeamTextSubmission.problem_id == problem_id, TeamTextSubmission.team_id == team_id).order_by(TeamTextSubmission.subproblem_no)).all()
    return [_serialize_report(row) for row in rows]


def save_team_text_submission(session: Session, problem_id: str, team_id: int, student_id: str, subproblem_no: int, content: str, revision: int) -> dict:
    """保存认领者的独立报告。

    参数：session 为数据库会话；problem_id 为题目编号；team_id 为已校验的小组编号；
    student_id 为提交者学号；subproblem_no 为已校验的认领区域；content 为完整文字内容；revision 为学生读取时的版本号。
    返回：保存后的报告字典；不判断报告内容的正确性。
    """
    if not content.strip():
        raise HTTPException(status_code=400, detail="请先填写文字内容")
    now = datetime.now(timezone.utc)
    # 首次提交创建记录，后续提交只更新学生实际读取过的版本。
    if revision == 0:
        session.add(TeamTextSubmission(problem_id=problem_id, team_id=team_id, student_id=student_id, subproblem_no=subproblem_no, content=content, updated_at=now))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=409, detail="该作答已提交新版本，请保留当前文字并重新加载自己的报告后再提交")
    else:
        result = session.exec(update(TeamTextSubmission).where(TeamTextSubmission.problem_id == problem_id, TeamTextSubmission.team_id == team_id, TeamTextSubmission.student_id == student_id, TeamTextSubmission.subproblem_no == subproblem_no, TeamTextSubmission.revision == revision).values(content=content, revision=revision + 1, updated_at=now))
        if result.rowcount != 1:
            session.rollback()
            raise HTTPException(status_code=409, detail="该作答已提交新版本，请保留当前文字并重新加载自己的报告后再提交")
        session.commit()
    return get_team_text_submission(session, problem_id, team_id, student_id)
