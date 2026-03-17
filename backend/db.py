import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text, inspect

# 使用 db 目录存储数据库，以便持久化 (因为 docker-compose 挂载了 /app/backend/db)
DATA_DIR = os.path.join(os.path.dirname(__file__), "db")
DB_PATH = os.path.join(DATA_DIR, "app.db")

# 确保 db 目录存在
os.makedirs(DATA_DIR, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def run_migrations():
    """
    检查并执行必要的数据库迁移
    """
    inspector = inspect(engine)
    
    # 1. 检查 problemstate 表是否存在
    if inspector.has_table("problemstate"):
        columns = [col["name"] for col in inspector.get_columns("problemstate")]
        
        # 迁移: 添加 is_public_view 字段
        if "is_public_view" not in columns:
            print("Migration: Adding 'is_public_view' to 'problemstate' table...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE problemstate ADD COLUMN is_public_view BOOLEAN DEFAULT 0"))
                conn.commit()
            print("Migration: Done.")

    # 2. 检查 teamsubproblemclaim 表是否存在
    if inspector.has_table("teamsubproblemclaim"):
        columns = [col["name"] for col in inspector.get_columns("teamsubproblemclaim")]

        # 迁移: 添加 switch_count 字段
        if "switch_count" not in columns:
            print("Migration: Adding 'switch_count' to 'teamsubproblemclaim' table...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE teamsubproblemclaim ADD COLUMN switch_count INTEGER DEFAULT 0"))
                conn.commit()
            print("Migration: Done.")


def init_db():
    """
    初始化数据库表结构（若不存在则创建）
    """
    from backend import models  # noqa: F401  确保模型被加载
    SQLModel.metadata.create_all(engine)
    
    # 执行动态迁移
    run_migrations()


def get_session():
    """
    获取数据库会话
    """
    with Session(engine) as session:
        yield session
