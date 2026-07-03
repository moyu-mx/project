"""数据分析公共工具。"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from src.config import CHARTS_DIR, DATA_CLEANED

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load_cleaned() -> pd.DataFrame:
    return pd.read_csv(DATA_CLEANED, parse_dates=["Order Date", "Ship Date"])


def save_fig(name: str) -> str:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / name
    try:
        plt.tight_layout()
    except Exception:
        plt.subplots_adjust(hspace=0.4, wspace=0.3)
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return str(path)
