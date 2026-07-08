"""项目路径与全局配置。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


if _is_frozen():
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", str(PROJECT_ROOT)))
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    BUNDLE_ROOT = PROJECT_ROOT


def bundled_path(*parts: str) -> Path:
    return BUNDLE_ROOT.joinpath(*parts)


def user_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


DATA_RAW = user_path("data.csv")
DATA_CLEANED = user_path("data", "cleaned", "superstore_clean.csv")
CHARTS_DIR = user_path("results", "charts")
DB_PATH = user_path("data", "superstore.db")
SQL_SCHEMA = bundled_path("sql", "schema.sql") if _is_frozen() else user_path("sql", "schema.sql")
CONFIG_DIR = user_path("config")
LOGS_DIR = user_path("logs")
WEB_DIR = bundled_path("web") if _is_frozen() else user_path("web")
PROMPT_PATH = bundled_path("prompts", "nl2sql.txt") if _is_frozen() else user_path("prompts", "nl2sql.txt")

for d in [
    user_path("data", "raw"),
    user_path("data", "cleaned"),
    CHARTS_DIR,
    LOGS_DIR,
    user_path("results"),
    CONFIG_DIR,
    user_path("sql", "templates"),
    user_path("prompts"),
    user_path("tests"),
    user_path("docs"),
]:
    d.mkdir(parents=True, exist_ok=True)


def _copy_file(src: Path, dst: Path) -> None:
    if not src.is_file() or dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree_files(src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.is_dir():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    for item in src_dir.iterdir():
        target = dst_dir / item.name
        if item.is_file() and not target.exists():
            shutil.copy2(item, target)


def ensure_runtime_assets() -> None:
    """打包版首次运行：将内置资源释放到 exe 同级目录。"""
    if not _is_frozen():
        return

    _copy_file(bundled_path("data", "superstore.db"), DB_PATH)
    _copy_file(
        bundled_path("data", "cleaned", "superstore_clean.csv"),
        DATA_CLEANED,
    )
    _copy_file(bundled_path("results", "forecast_report.json"), user_path("results", "forecast_report.json"))
    _copy_tree_files(bundled_path("results", "charts"), CHARTS_DIR)
    _copy_tree_files(bundled_path("config"), CONFIG_DIR)

    llm_example = bundled_path("config", "llm_keys.yaml.example")
    _copy_file(llm_example, CONFIG_DIR / "llm_keys.yaml.example")
