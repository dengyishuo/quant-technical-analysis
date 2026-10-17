#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成交互图所需的数据包。

28 个指标章都画同一只标的（贵州茅台）的同一段行情，只有叠加的指标不同，
所以行情只存一份，各章另存一条指标序列。

每个指标要决定画在哪个窗格：

  price  与 K 线同窗格叠加（均线、SAR、通道这类与价格同量纲的）
  sub    独立窗格（震荡、波动率这类量纲不同的）
  hist   独立窗格，用柱状（MACD 柱）

价格窗格里画原始值（价格量级），独立窗格里画已无量纲化的因子，
与正文表格检验的是同一个量。

产出：电子书/chart-data.json
用法：python3 scripts/build_chart_data.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from equant_spec import SPEC  # noqa: E402

import ettr  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "电子书" / "chart-data.json"

CODE = "600519.SS"

# 画在哪个窗格，以及图例文字
PANES = {
    9:  ("price", "SMA(20)"),
    10: ("price", "EMA(12)"),
    11: ("price", "WMA(10)"),
    12: ("price", "DEMA(20)"),
    13: ("price", "ZLEMA(20)"),
    14: ("sub",   "DMA（快慢均线差）"),
    15: ("price", "BBI(3/6/12/24)"),
    16: ("hist",  "MACD 柱"),
    17: ("sub",   "DI+ − DI−"),
    18: ("sub",   "ADX(14)"),
    19: ("price", "SAR"),
    21: ("sub",   "RSI(14)"),
    22: ("sub",   "KDJ 之 J"),
    23: ("sub",   "CCI(20)"),
    24: ("sub",   "WPR(14)"),
    25: ("sub",   "ROC(12)"),
    26: ("sub",   "CMO(14)"),
    27: ("sub",   "DPO(20)"),
    28: ("sub",   "SMI"),
    30: ("sub",   "ATR(14) / 价格"),
    31: ("sub",   "历史波动率(20)"),
    32: ("sub",   "布林 %B"),
    33: ("price", "肯特纳中轨"),
    34: ("price", "包络基准线 SMA(20)"),
    36: ("sub",   "OBV 10 日变化率"),
    37: ("sub",   "CMF(20)"),
    38: ("sub",   "成交量震荡器"),
    39: ("price", "EVWMA(10)"),
}


def build_indicator(df: pd.DataFrame, s: dict) -> pd.Series:
    """按规格算指标，返回与 df 对齐的序列。"""
    d = df.copy()
    for fn, kw in s["py"]:
        d = getattr(ettr, fn)(d, **kw)

    pre = s.get("pre")
    if pre == "py_dma":
        d["DMA"] = d["SMA_10"] - d["SMA_50"]
    elif pre == "py_bbi":
        d["BBI"] = (d["SMA_3"] + d["SMA_6"] + d["SMA_12"] + d["SMA_24"]) / 4
    elif pre == "py_vo":
        d["VO"] = d["SMA_5"] / d["SMA_20"] - 1

    col = s["py_col"]
    pane = PANES[s["ch"]][0]

    if pane == "price":
        # 与价格同量纲，画原值
        return d[col]
    if s.get("shift"):
        return d.groupby("code")[col].pct_change(10)
    return eval(s["factor"].format(c='d["%s"]' % col, d="d."), {"d": d, "np": np})


def main() -> None:
    blue = pd.read_parquet(ROOT / "data/parquet/panel_blue_chip.parquet")
    m = blue[blue["code"] == CODE].sort_values("date").reset_index(drop=True)

    # 行情只存一份
    ohlc = {
        "t": [str(pd.Timestamp(d).date()) for d in m["date"]],
        "o": m["open"].round(2).tolist(),
        "h": m["high"].round(2).tolist(),
        "l": m["low"].round(2).tolist(),
        "c": m["close"].round(2).tolist(),
        "v": [int(x) for x in m["volume"].fillna(0)],
    }

    chapters = {}
    for s in SPEC:
        ch = s["ch"]
        pane, label = PANES[ch]
        ser = build_indicator(m, s)
        # 保留三位小数，nan 转 null
        vals = [None if pd.isna(x) else round(float(x), 4) for x in ser]
        chapters[str(ch)] = {
            "pane": pane,
            "label": label,
            "name": s["name"],
            "vals": vals,
        }

    payload = {"symbol": CODE, "ohlc": ohlc, "chapters": chapters}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    kb = OUT.stat().st_size / 1024
    print("已写 %s（%.0f KB）" % (OUT.relative_to(ROOT), kb))
    print("行情 %d 根 K 线，%d 章指标" % (len(ohlc["t"]), len(chapters)))
    for ch, v in list(chapters.items())[:3]:
        valid = sum(1 for x in v["vals"] if x is not None)
        print("  第%03d章 %-10s %-6s 有效 %d" % (int(ch), v["name"], v["pane"], valid))


if __name__ == "__main__":
    main()
