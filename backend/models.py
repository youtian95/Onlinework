from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


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


class ProblemState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    problem_id: str = Field(index=True, unique=True)
    
    # Display state
    title: Optional[str] = None
    
    # Lifecycle
    is_visible: bool = Field(default=False)   # Published vs Draft
    deadline: Optional[datetime] = None       # Auto termination time
    is_deleted: bool = Field(default=False)   # Recycle bin
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SystemSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
