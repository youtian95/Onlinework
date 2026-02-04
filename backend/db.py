import os
from sqlmodel import SQLModel, create_engine, Session

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")

# 确保 data 目录存在
os.makedirs(DATA_DIR, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db():
    """
    初始化数据库表结构（若不存在则创建）
    """
    from backend import models  # noqa: F401  确保模型被加载
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    获取数据库会话
    """
    with Session(engine) as session:
        yield session
