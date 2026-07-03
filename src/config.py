"""项目路径与全局配置。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data.csv"
DATA_CLEANED = PROJECT_ROOT / "data" / "cleaned" / "superstore_clean.csv"
CHARTS_DIR = PROJECT_ROOT / "results" / "charts"
DB_PATH = PROJECT_ROOT / "data" / "superstore.db"
SQL_SCHEMA = PROJECT_ROOT / "sql" / "schema.sql"
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"

for d in [
    PROJECT_ROOT / "data" / "raw",
    PROJECT_ROOT / "data" / "cleaned",
    CHARTS_DIR,
    LOGS_DIR,
    PROJECT_ROOT / "sql" / "templates",
    PROJECT_ROOT / "prompts",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "docs",
]:
    d.mkdir(parents=True, exist_ok=True)
