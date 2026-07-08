"""ECharts 图例与数据注记样式。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

LABEL_COLOR = "#ffffff"


def _merge_text_style(style: dict | None, color: str = LABEL_COLOR) -> dict:
    merged = dict(style or {})
    merged["color"] = color
    return merged


def apply_legend_label_style(option: dict[str, Any] | None) -> dict[str, Any] | None:
    """为图例与数据注记设置白色文字，并移除图表内嵌标题。"""
    if not option:
        return option

    opt = deepcopy(option)
    opt.pop("title", None)
    legend = opt.get("legend")
    if legend:
        if isinstance(legend, list):
            opt["legend"] = [
                {**item, "textStyle": _merge_text_style(item.get("textStyle"))}
                for item in legend
            ]
        elif isinstance(legend, dict):
            opt["legend"] = {**legend, "textStyle": _merge_text_style(legend.get("textStyle"))}

    for series in opt.get("series") or []:
        if not isinstance(series, dict):
            continue
        label = series.get("label")
        if label is False:
            continue
        if isinstance(label, dict):
            series["label"] = {**label, "color": LABEL_COLOR}
        else:
            series["label"] = {"color": LABEL_COLOR}

        if series.get("type") == "pie" and isinstance(series.get("data"), list):
            for item in series["data"]:
                if not isinstance(item, dict):
                    continue
                item_label = item.get("label")
                if item_label is False:
                    continue
                if isinstance(item_label, dict):
                    if item_label.get("show") is False:
                        continue
                    item["label"] = {**item_label, "color": LABEL_COLOR}
                else:
                    item["label"] = {"color": LABEL_COLOR}

    graphic = opt.get("graphic")
    if graphic:
        items = graphic if isinstance(graphic, list) else [graphic]
        for item in items:
            if not isinstance(item, dict):
                continue
            style = item.get("style")
            if isinstance(style, dict) and "text" in style:
                style["fill"] = LABEL_COLOR

    return opt
