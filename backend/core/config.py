
import os
from pathlib import Path
from dotenv import load_dotenv

# 从项目根目录加载 .env.secret 文件 (.env 是环境目录，所以改用这个名字)
# config.py 在 backend/core/，所以往上找 3 层到达根目录
env_path = Path(__file__).resolve().parent.parent.parent / ".env.secret"
load_dotenv(dotenv_path=env_path)

# 管理员密码（优先从环境变量读取，默认值为 admin123）
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# JWT 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-please-change-it")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 1  # 1 day

# System Paths
# config.py is in backend/core, so parent.parent is backend
BACKEND_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BACKEND_DIR / "public"

if not PUBLIC_DIR.exists():
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)


# 归档文件夹
ARCHIVES_DIR = "archives"
if not os.path.exists(ARCHIVES_DIR):
    os.makedirs(ARCHIVES_DIR)
