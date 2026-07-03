"""一键运行全部分析并生成图表。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.analysis import (
    customers,
    profit,
    regions,
    rfm,
    sales,
    seasonality,
    shipping,
)
from src.cleaning.clean_data import run as run_cleaning


def main() -> None:
    print("=== 阶段1: 数据清洗 ===")
    run_cleaning()
    print("=== 阶段2: 数据分析 ===")
    profit.run()
    sales.run()
    regions.run()
    seasonality.run()
    customers.run()
    rfm.run()
    shipping.run()
    print("=== 全部分析完成，图表见 results/charts/ ===")


if __name__ == "__main__":
    main()
