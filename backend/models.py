from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint


class Student(SQLModel, table=True):
    """
    表示系统中的学生或用户账户。
    包含基本身份信息、状态（启用/测试/删除）和登录凭证。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True, unique=True)
    name: Optional[str] = None
    enabled: bool = True
    is_test: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    password_hash: Optional[str] = None


class Attempt(SQLModel, table=True):
    """
    记录学生对特定题目输入的答题记录。
    跟踪答题次数、正确状态、最后的答案以及更新时间。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    problem_id: str = Field(index=True)
    input_id: str = Field(index=True)
    attempts: int = 0
    correct: bool = False
    last_answer: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProblemSubmission(SQLModel, table=True):
    """
    记录学生上传的作业文件（如PDF）提交记录。
    保存文件路径和原始文件名等信息。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    problem_id: str = Field(index=True)
    pdf_path: str
    original_filename: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProblemState(SQLModel, table=True):
    """
    管理题目的元数据和生命周期状态。
    包括可见性（是否发布）、截止时间和回收站状态。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True, unique=True)
    
    # Display state
    title: Optional[str] = None
    
    # Lifecycle
    is_visible: bool = Field(default=False)   # Published vs Draft
    is_public_view: bool = Field(default=False) # Guest view allowed
    deadline: Optional[datetime] = None       # Auto termination time
    is_deleted: bool = Field(default=False)   # Recycle bin
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TeamWorkConfig(SQLModel, table=True):
    """
    特定题目的团队合作配置信息。
    定义了该题目的团队数量、每个团队的最大规模及子题目数量。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True, unique=True)
    team_count: int = Field(default=0, ge=0)
    team_size: int = Field(default=0, ge=0)
    subproblem_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Team(SQLModel, table=True):
    """
    表示为特定问题创建的一个具体团队。
    存储团队编号、名称和队伍容纳人数上限。
    """
    __table_args__ = (
        UniqueConstraint("problem_id", "team_no", name="uq_team_problem_no"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True)
    team_no: int = Field(index=True, ge=1)
    name: Optional[str] = None
    max_members: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TeamMember(SQLModel, table=True):
    """
    关联学生与特定题目所在团队的关系记录。
    确保每个题目每个学生只能加入一个团队。
    """
    __table_args__ = (
        UniqueConstraint("problem_id", "student_id", name="uq_teammember_problem_student"),
        UniqueConstraint("problem_id", "team_id", "student_id", name="uq_teammember_problem_team_student"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True)
    team_id: int = Field(index=True)
    student_id: str = Field(index=True)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TeamSubproblemClaim(SQLModel, table=True):
    """
    记录团队协作题目中被学生认领的子题目状态。
    约束每个同学只能认领一个子题，且每个子题只能被一位同学认领。
    """
    __table_args__ = (
        UniqueConstraint("problem_id", "team_id", "student_id", name="uq_claim_problem_team_student"),
        UniqueConstraint("problem_id", "team_id", "subproblem_no", name="uq_claim_problem_team_subproblem"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True)
    team_id: int = Field(index=True)
    student_id: str = Field(index=True)
    subproblem_no: int = Field(index=True, ge=1)
    switch_count: int = Field(default=0, ge=0)
    claimed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TeamAttempt(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("problem_id", "team_id", "student_id", "input_id", name="uq_teamattempt_scope_input"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True)
    team_id: int = Field(index=True)
    student_id: str = Field(index=True)
    input_id: str = Field(index=True)
    attempts: int = 0
    correct: bool = False
    last_answer: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TeamSubmission(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("problem_id", "team_id", "student_id", name="uq_teamsub_scope_student"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True)
    team_id: int = Field(index=True)
    student_id: str = Field(index=True)
    pdf_path: str
    original_filename: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SystemSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
