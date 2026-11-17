# 分组文字作业回归测试：在独立内存数据库中配置队伍并调用接口，验证认领、个人作答隔离、截止和备份恢复。
# 使用方式：python -m unittest discover -s tests -p test_team_text.py；不读写实际业务数据库。
# 输入为测试学生及文字报告，输出 unittest 断言结果。
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from backend.models import Attempt, ProblemState, Student, Team, TeamAttempt, TeamMember, TeamSubproblemClaim, TeamTextSubmission
from backend.routers import admin, export, problems
from backend.services import problems as problem_service
from backend.services.team_text import get_team_text_submission


class TeamTextTests(unittest.TestCase):
    """验证分组文字作业的业务行为，所有数据仅存在于测试数据库。"""

    def setUp(self):
        """为每个测试新建数据库、三个学生及两个小组。"""
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        # 使用受版本控制的独立题面，测试不依赖被 Git 忽略的实际题库。
        fixture_dir = str(Path(__file__).parent / "fixtures")
        for module in (problems, problem_service):
            patcher = patch.object(module, "PROBLEMS_DIR", fixture_dir)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.problem_id = "team-text"
        self.students = [Student(student_id=f"text-student-{i}", name=f"测试学生{i}") for i in range(3)]
        self.session.add_all(self.students)
        self.session.add(ProblemState(problem_id=self.problem_id, is_visible=True))
        self.session.commit()
        self.config, _ = admin._save_teamwork_config(self.session, self.problem_id, 2, 4)
        self.teams = self.session.exec(select(Team).order_by(Team.team_no)).all()
        for i, student in enumerate(self.students):
            self.session.add(TeamMember(problem_id=self.problem_id, team_id=self.teams[0 if i < 2 else 1].id, student_id=student.student_id))
        self.session.commit()

    def tearDown(self):
        """关闭测试会话并释放内存数据库。"""
        self.session.close()
        self.engine.dispose()

    def claim(self, student_index=0, subproblem_no=1, force_switch=False):
        """认领测试区域；student_index 为学生索引，subproblem_no 为区域号，force_switch 为确认切换标记。"""
        return problems.claim_subproblem(self.problem_id, problems.ClaimSubproblemRequest(subproblem_no=subproblem_no, force_switch=force_switch), self.students[student_index], self.session)

    def submit(self, student_index=0, content="项目一\n分析与结论：保留原连接。", revision=0, subproblem_no=1):
        """提交测试报告；student_index 为学生索引，content 为报告，revision 为已读版本，subproblem_no 为目标区域。"""
        return problems.submit_team_text(self.problem_id, problems.TeamTextRequest(subproblem_no=subproblem_no, content=content, revision=revision), self.students[student_index], self.session)["text_submission"]

    def assert_http_error(self, code, function, *args, **kwargs):
        """断言接口错误；code 为预期状态码，function 为目标函数，args 和 kwargs 为调用参数。"""
        with self.assertRaises(HTTPException) as context:
            function(*args, **kwargs)
        self.assertEqual(context.exception.status_code, code)

    def test_individual_reports_require_claims_without_grading(self):
        """每人先认领再提交，各自内容互不覆盖，组内可查看而组外隔离，不产生判题记录。"""
        self.assertEqual(self.config.subproblem_count, 3)
        self.assert_http_error(403, self.submit)
        self.claim(0, 1)
        self.claim(1, 2)
        report = self.submit()
        teammate_report = self.submit(1, "另一位组员的报告", subproblem_no=2)
        self.assert_http_error(403, self.submit, 0, "代写区域二", subproblem_no=2)
        member_view = problems.get_problem(self.problem_id, self.students[1], self.session)
        other_view = problems.get_problem(self.problem_id, self.students[2], self.session)
        self.assertEqual(member_view["text_submissions"][0]["content"], report["content"])
        self.assertEqual(member_view["text_submissions"][1]["content"], teammate_report["content"])
        self.assertEqual(member_view["my_claim_subproblem"], 2)
        self.assertEqual(other_view["text_submissions"], [])
        self.assertEqual(len(member_view["subproblems"]), 3)
        self.assertEqual(member_view["input_ids"], [])
        admin_view = admin.get_admin_problem_content(self.problem_id, team_id=self.teams[0].id, session=self.session)
        self.assertEqual(admin_view["text_submissions"][0]["content"], report["content"])
        updated = self.submit(0, "本人补充后的完整报告\n第二段", 1)
        self.assertEqual(updated["revision"], 2)
        self.assertEqual(updated["student_id"], self.students[0].student_id)
        self.assertEqual(get_team_text_submission(self.session, self.problem_id, self.teams[0].id, self.students[1].student_id)["content"], teammate_report["content"])
        for model in (Attempt, TeamAttempt):
            self.assertEqual(self.session.exec(select(model)).all(), [])
        listed = problems.list_problems(self.students[1], self.session)
        item = next(row for row in listed if row["id"] == self.problem_id)
        self.assertTrue(item["text_submitted"])
        self.assertNotIn("total_score", item)
        self.assertEqual(problem_service.get_teamwork_personal_ranking(self.session, self.problem_id), [])
        self.assertEqual(problem_service.get_teamwork_team_ranking(self.session, self.problem_id), [])
        with patch.dict(problem_service._RANKING_CACHE, {}, clear=True):
            self.assertTrue(all(row["total_possible"] == 0 for row in problem_service.get_total_ranking(self.session)))

    def test_stale_submissions_preserve_newest_report(self):
        """同一学生不同页面的旧版本提交返回冲突，不覆盖已提交内容。"""
        self.claim()
        self.submit()
        self.assert_http_error(409, self.submit, 0, "旧页面首次提交", 0)
        self.submit(0, "最新报告", 1)
        self.assert_http_error(409, self.submit, 0, "旧版本覆盖", 1)
        self.assertEqual(get_team_text_submission(self.session, self.problem_id, self.teams[0].id, self.students[0].student_id)["content"], "最新报告")

    def test_deadline_membership_and_no_checker(self):
        """空内容、未入组、截止和未发布不可提交，普通判题入口也拒绝文字作业。"""
        self.claim()
        self.assert_http_error(400, self.submit, content=" \n ")
        outsider = Student(student_id="outsider")
        self.assert_http_error(403, problems.submit_team_text, self.problem_id, problems.TeamTextRequest(subproblem_no=1, content="报告"), outsider, self.session)
        self.assert_http_error(400, problems.submit_answer, problems.SubmitRequest(student_id=self.students[0].student_id, problem_id=self.problem_id, answers={"report": "文字"}), self.session)
        state = self.session.exec(select(ProblemState)).first()
        state.deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.session.add(state)
        self.session.commit()
        self.assert_http_error(400, self.submit)
        self.assertTrue(problems.get_problem(self.problem_id, self.students[0], self.session)["is_terminated"])
        state.deadline = None
        state.is_visible = False
        self.session.add(state)
        self.session.commit()
        self.assert_http_error(403, self.submit)

    def test_backup_restore_and_ordinary_team_config(self):
        """文字及换行能够完整备份恢复，普通分组作业仍保持每人一个子题。"""
        self.claim()
        report = self.submit(content="项目二\n多行文字，中文与符号：N=1600 kN\n\n分工：甲、乙。")
        ordinary, _ = admin._save_teamwork_config(self.session, "ordinary-test", 1, 3)
        self.assertEqual(ordinary.subproblem_count, 3)
        # 本测试不包含上传文件，用不存在的隔离目录避免遍历真实业务附件。
        with patch.object(export, "PUBLIC_DIR", Path(__file__).parent / "_no_uploaded_files"):
            backup = export.create_db_dump_bytes(self.session)
            export.restore_db_from_bytes(backup, self.session)
        restored = self.session.exec(select(TeamTextSubmission)).one()
        self.assertEqual(restored.content, report["content"])
        self.assertEqual(restored.revision, report["revision"])
        self.assertEqual(restored.student_id, report["student_id"])
        self.assertEqual(restored.subproblem_no, 1)

    def test_claim_switch_and_team_switch_clear_only_own_report(self):
        """认领不可抢占；换认领或换组清理本人旧报告，保留其他组员内容。"""
        self.claim(0, 1)
        self.claim(1, 2)
        self.assert_http_error(409, self.claim, 1, 1)
        self.submit()
        self.submit(1, "组员二的独立报告", subproblem_no=2)
        self.claim(0, 3, True)
        self.assert_http_error(403, self.submit, subproblem_no=1)
        self.submit(subproblem_no=3)
        problems.join_team(self.problem_id, problems.JoinTeamRequest(team_no=2, force_switch=True), self.students[0], self.session)
        rows = self.session.exec(select(TeamTextSubmission)).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].student_id, self.students[1].student_id)

    def test_explicit_subproblem_template_and_repair_zero_count(self):
        """模板中三个项目对应三个认领子题，不受组员人数四人的影响。"""
        self.config.subproblem_count = 0
        self.session.add(self.config)
        self.session.commit()
        view = problems.get_problem(self.problem_id, self.students[0], self.session)
        self.assertEqual(len(view["subproblems"]), 3)
        self.assertEqual(self.config.subproblem_count, 3)
        self.assertEqual([block["subproblem_no"] for block in view["subproblems"]], [1, 2, 3])

    def test_default_team_config_initializes_before_claiming(self):
        """题目直接加入目录时，管理端和学生端都能按脚本默认配置启用分组。"""
        fresh_engine = create_engine("sqlite://", poolclass=StaticPool)
        SQLModel.metadata.create_all(fresh_engine)
        try:
            with Session(fresh_engine) as session:
                overview = admin.get_teamwork_overview(self.problem_id, session)
                self.assertEqual(overview["config"]["subproblem_count"], 3)
                self.assertEqual(len(overview["teams"]), 2)
                team_info = problems.get_my_team_info(self.problem_id, self.students[0], session)
                self.assertTrue(team_info["teamwork_enabled"])
                self.assertFalse(team_info["joined"])
        finally:
            fresh_engine.dispose()


if __name__ == "__main__":
    unittest.main()
