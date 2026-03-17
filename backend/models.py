from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True, unique=True)
    name: Optional[str] = None
    enabled: bool = True
    is_test: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    password_hash: Optional[str] = None


class Attempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    problem_id: str = Field(index=True)
    input_id: str = Field(index=True)
    attempts: int = 0
    correct: bool = False
    last_answer: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProblemSubmission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    problem_id: str = Field(index=True)
    pdf_path: str
    original_filename: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProblemState(SQLModel, table=True):
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
    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True, unique=True)
    team_count: int = Field(default=0, ge=0)
    team_size: int = Field(default=0, ge=0)
    subproblem_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Team(SQLModel, table=True):
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
