"""大模型结构化回复 Schema 与校验。"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ChartTemplate = Literal["table", "bar", "line", "pie", "horizontal_bar"]

VALID_TEMPLATES = ("table", "bar", "line", "pie", "horizontal_bar")

TEMPLATE_LABELS = {
    "table": "数据表格",
    "bar": "柱状图",
    "line": "折线图",
    "pie": "饼状图",
    "horizontal_bar": "条形图",
}


class QueryDisplaySpec(BaseModel):
    """查询结果展示规格，由大模型或本地引擎生成。"""

    template: ChartTemplate = "table"
    chart_title: str = "查询结果"
    x_column: str | None = None
    y_column: str | None = None
    y_columns: list[str] | None = None
    value_min: float = Field(default=0.1, ge=0)
    summary: str = ""

    @field_validator("template", mode="before")
    @classmethod
    def normalize_template(cls, v: str) -> str:
        if v not in VALID_TEMPLATES:
            return "table"
        return v

    @field_validator("chart_title", "summary", mode="before")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return (v or "").strip()


class StructuredChatResponse(BaseModel):
    """大模型必须返回的完整 JSON 结构。"""

    sql: str
    template: ChartTemplate = "table"
    chart_title: str
    x_column: str | None = None
    y_column: str | None = None
    y_columns: list[str] | None = None
    value_min: float = 0.1
    summary: str = ""

    def to_display_spec(self) -> QueryDisplaySpec:
        return QueryDisplaySpec(
            template=self.template,
            chart_title=self.chart_title,
            x_column=self.x_column,
            y_column=self.y_column,
            y_columns=self.y_columns,
            value_min=self.value_min,
            summary=self.summary,
        )


JSON_SCHEMA_HINT = """
你必须只输出一个 JSON 对象，不要 Markdown，不要其他文字。格式如下：
{
  "sql": "SELECT ... LIMIT 100",
  "template": "bar",
  "chart_title": "2013年各区域销售额",
  "x_column": "维度列名",
  "y_column": "数值列名",
  "y_columns": null,
  "value_min": 0.1,
  "summary": "一句话回答用户问题"
}

template 只能是：table | bar | line | pie | horizontal_bar
- pie：占比、构成、分布（类别≤10）
- line：趋势、月度/年度变化
- bar：类别对比、排名
- horizontal_bar：类别较多时的横向对比
- table：多列明细或不适合图表时
value_min 固定为 0.1，表示仅展示数值大于 0.1 的记录。
"""


def parse_structured_json(text: str) -> StructuredChatResponse | None:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return StructuredChatResponse.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return StructuredChatResponse.model_validate(json.loads(m.group()))
            except (json.JSONDecodeError, ValueError):
                return None
    return None
