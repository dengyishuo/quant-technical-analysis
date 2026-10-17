#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把跑出来的图、表与解读插入指标章正文。

三类插入：
  1. 「代码实现」小节末尾：指标图 + 图注
  2. 「截面选股能力」小节末尾：IC 结果表 + 解读
  3. 「择时能力」小节末尾：分位收益表 + 解读

表格数据由本脚本用 eQuant 重算一次得到（与章内代码同函数同参数），
再把 DataFrame 转成 Markdown 表。图直接从 assets/figures 引用。

为了不让电子书变成一堆外链图片，图片在编译阶段会内联成 base64，
这里只写相对路径。

用法：python3 scripts/insert_results.py [--dry]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import warnings

import gc
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from equant_spec import SPEC  # noqa: E402

import ettr  # noqa: E402
import efactorcraft as efc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIG = "assets/figures"

BLOCK_RE = re.compile(r"^```(r|python)[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)


# ───────────────────────── 工具 ─────────────────────────

def md_table(df: pd.DataFrame, float_fmt="{:.4f}") -> str:
    """按列决定小数位：t 值两位，ICIR 三位，其余四位。"""
    """把 DataFrame 转成 Markdown 表，不依赖 tabulate。"""
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    if df.index.name or not isinstance(df.index, pd.RangeIndex):
        idx_name = df.index.name or ""
        df = df.reset_index()
        if idx_name and str(df.columns[0]) == "index":
            df = df.rename(columns={df.columns[0]: idx_name})
    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join(["---"] * len(df.columns)) + "|"
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c, v in zip(df.columns, r):
            if isinstance(v, (float, np.floating)):
                if pd.isna(v):
                    cells.append("")
                elif "t 值" in str(c):
                    cells.append("%.2f" % v)
                elif "ICIR" in str(c):
                    cells.append("%.3f" % v)
                else:
                    cells.append(float_fmt.format(v))
            elif isinstance(v, (int, np.integer)):
                cells.append(str(int(v)))
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([head, sep] + rows)


def compute(s: dict, panel: pd.DataFrame):
    """按规格重算因子，返回带 forward 收益的面板。"""
    d = panel.copy()
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
    if s.get("shift"):
        d = d.sort_values(["code", "date"])
        d["f"] = d.groupby("code")[col].pct_change(10)
    else:
        expr = s["factor"].format(c='d["%s"]' % col, d="d.")
        d["f"] = eval(expr, {"d": d, "np": np})   # 表达式求值，不是字符串

    d = efc.add_next_return(d, periods=(1, 5, 20))
    return d


def ic_table(d: pd.DataFrame) -> tuple[str, dict]:
    """IC 汇总表：均值、标准差、ICIR、t、胜率。一次调用算三个前向期。"""
    fwds = ["forward_1", "forward_5", "forward_20"]
    ic = efc.ic_analysis(d, factor_cols="f", forward_cols=fwds, method="spearman")
    frame = ic["f"]

    rows = []
    for fwd in fwds:
        key = [c for c in frame.columns if c.replace("fwd", "forward_") == fwd]
        if not key:
            continue
        ser = frame[key[0]].dropna()
        if len(ser) < 10:
            continue
        m, sd = ser.mean(), ser.std()
        rows.append({
            "前向期": fwd.replace("forward_", "T+"),
            "IC 均值": round(m, 4),
            "IC 标准差": round(sd, 4),
            "ICIR": round(m / sd, 3) if sd else np.nan,
            "t 值": round(m / sd * np.sqrt(len(ser)), 2) if sd else np.nan,
            "IC>0 占比": round((ser > 0).mean(), 3),
            "期数": len(ser),
        })
    df = pd.DataFrame(rows)
    stats = {r["前向期"]: r for _, r in df.iterrows()} if len(df) else {}
    return (md_table(df) if len(df) else ""), stats


def quantile_table(d: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    q = efc.quantile_analysis(d, factor_col="f", forward_col="forward_5", n_groups=5)
    sm = q["summary"].copy()
    sm["group"] = sm["group"].astype(int)
    sm = sm.rename(columns={"group": "分组", "mean": "平均收益", "std": "标准差", "count": "期数"})
    for c in ["平均收益", "标准差"]:
        sm[c] = sm[c].map(lambda x: "%+.4f" % x)
    return md_table(sm), q["summary"]


def timing_table(t: pd.DataFrame) -> str:
    t = t.copy()
    t["q"] = pd.qcut(t["f"], 5, labels=False) + 1
    g = t.groupby("q")["forward_5"].agg(["mean", "count"]).reset_index()
    g.columns = ["分位", "未来 5 日均值", "样本数"]
    g["未来 5 日均值"] = g["未来 5 日均值"].map(lambda x: "%+.4f" % x)
    return md_table(g)


# ───────────────────────── 解读文字 ─────────────────────────

def interp_ic(s: dict, stats: dict) -> str:
    if not stats:
        return ""
    keys = list(stats)
    first = stats[keys[0]]
    ic = first["IC 均值"]
    icir = first["ICIR"]
    t = first["t 值"]

    if abs(t) < 2:
        judge = "在常规门槛下不显著"
    elif abs(t) < 3:
        judge = "刚过显著线，属于临界"
    else:
        judge = "在统计上显著"

    direction = "正向" if ic > 0 else "反向"
    return (
        "表里最该看的是 t 值，不是 IC 均值。这个因子以 T+1 为主口径，IC 均值 %.4f、"
        "ICIR %.3f、t 值 %.2f，%s，方向为%s。按第 007 章给出的日频门槛（ICIR 0.13 对应 t≈2），"
        "这个结果的含义是：%s。\n\n"
        "需要提醒的是，这只说明排序与未来收益之间存在可测的关联，不代表扣掉成本后还能剩下收益。"
        "横截面 IC 检验的是“买哪只”，不负责“值不值得交易”。"
        % (ic, icir, t, judge, direction,
           "信号强度已经越过噪声能解释的范围，值得进入下一步检验"
           if abs(t) >= 2 else "还看不出与噪声的区别，不能据此构造策略")
    )


def interp_quantile(s: dict, sm: pd.DataFrame) -> str:
    if sm is None or len(sm) < 5:
        return ""
    means = sm.sort_values("group")["mean"].values
    best, worst = int(np.argmax(means)) + 1, int(np.argmin(means)) + 1
    spread = means[-1] - means[0]
    mono = np.corrcoef(np.arange(1, 6), means)[0, 1]

    if abs(mono) > 0.8:
        shape = "接近单调"
    elif abs(mono) > 0.4:
        shape = "有方向但不严格单调"
    else:
        shape = "没有明显单调性"

    return (
        "五档分层看的是形状，不是单点。最高一档在第 %d 组、最低在第 %d 组，"
        "两端相差 %+.2f%%，组序号与平均收益的秩相关为 %.2f，%s。\n\n"
        "分层比 IC 更接近实盘，因为它直接给出“买最高档、卖最低档”的收益差。"
        "但这里的数字是毛收益，且没有考虑涨跌停买不进、停牌卖不出的情形，"
        "真实可得的差额会小于表中所列。"
        % (best, worst, spread * 100, mono, shape)
    )


def interp_timing(s: dict, g: pd.DataFrame) -> str:
    if g is None or len(g) < 5:
        return ""
    means = g.sort_values("group")["mean"].values
    spread = means[-1] - means[0]
    return (
        "择时口径与截面不同：这里只有一个标的，看的是同一标的在不同分位下的未来收益。"
        "最高与最低分位相差 %+.2f%%。单标的样本有限，这个差额很容易被一两段行情主导，"
        "只能作为方向参考。\n\n"
        "真正做择时要问的是三件事：分位阈值是否稳定、换手是否可控、扣成本后是否还有剩余。"
        "三者缺一，择时信号就只是图上好看。"
        % (spread * 100)
    )


# ───────────────────────── 插入 ─────────────────────────

def figure_block(ch: int, caption: str, fname: str = "indicator.png") -> str:
    p = ROOT / FIG / ("ch%03d" % ch) / fname
    if not p.exists():
        return ""
    return '\n![%s](../%s/ch%03d/%s)\n\n<p class="figcap">%s</p>\n' % (
        caption, FIG, ch, fname, caption)


def strip_old(text: str, tag: str) -> str:
    """删掉本脚本上次插入的块，避免重复。"""
    pat = re.compile(r"\n<!-- %s:start -->.*?<!-- %s:end -->\n" % (tag, tag), re.S)
    return pat.sub("\n", text)


def insert_after_section(text: str, section: str, payload: str, tag: str) -> str:
    """把 payload 插到某个二级小节的末尾（下一个 ## 之前）。"""
    if not payload.strip():
        return text
    m = re.search(r"^## %s[ \t]*$" % re.escape(section), text, re.M)
    if not m:
        return text
    nxt = re.search(r"^## ", text[m.end():], re.M)
    pos = m.end() + (nxt.start() if nxt else len(text) - m.end())
    block = "\n<!-- %s:start -->\n%s\n<!-- %s:end -->\n" % (tag, payload.strip(), tag)
    return text[:pos].rstrip("\n") + "\n" + block + "\n" + text[pos:].lstrip("\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="", help="只处理指定章号，逗号分隔")
    args = ap.parse_args()

    panel = pd.read_parquet(ROOT / "data/parquet/panel.parquet")
    panel = panel[(panel["date"] >= "2023-01-01") & (panel["date"] <= "2025-06-01")]
    idx = pd.read_parquet(ROOT / "data/parquet/index_daily.parquet")
    idx = idx[idx["code"] == "510300.SS"].sort_values("date")

    files = {int(re.match(r"第(\d+)章", f.name).group(1)): f
             for f in ROOT.glob("模块*/第*.md") if re.match(r"第(\d+)章", f.name)}

    done = 0
    only = {int(x) for x in args.only.split(",") if x.strip()}
    for s in SPEC:
        if only and s["ch"] not in only:
            continue
        f = files.get(s["ch"])
        if f is None:
            continue
        text = f.read_text(encoding="utf-8")
        for tag in ("fig-indicator", "tab-ic", "tab-quantile", "tab-timing"):
            text = strip_old(text, tag)

        d = compute(s, panel)
        ic_md, stats = ic_table(d)
        q_md, q_sm = quantile_table(d)

        # 择时：ETF 上算同一指标
        t = idx.copy()
        for fn, kw in s["py"]:
            t = getattr(ettr, fn)(t, **kw)
        pre = s.get("pre")
        if pre == "py_dma":
            t["DMA"] = t["SMA_10"] - t["SMA_50"]
        elif pre == "py_bbi":
            t["BBI"] = (t["SMA_3"] + t["SMA_6"] + t["SMA_12"] + t["SMA_24"]) / 4
        elif pre == "py_vo":
            t["VO"] = t["SMA_5"] / t["SMA_20"] - 1
        col = s["py_col"]
        if s.get("shift"):
            t["f"] = t[col].pct_change(10)
        else:
            expr = s["factor"].format(c='t["%s"]' % col, d="t.")
            t["f"] = eval(expr, {"t": t, "np": np})
        t["forward_5"] = t["close"].shift(-5) / t["close"] - 1
        tg = t.dropna(subset=["f", "forward_5"])
        tm_md = timing_table(tg) if len(tg) > 50 else ""

        fig = figure_block(s["ch"], "图 %d-1　%s在贵州茅台上的读数（2023-01 至 2025-06）"
                           % (s["ch"], s["name"]))
        payload_fig = fig
        payload_ic = ("**计算结果**\n\n" + ic_md + "\n\n" + interp_ic(s, stats)) if ic_md else ""
        payload_q = ("**五档分层**\n\n" + q_md + "\n\n" + interp_quantile(s, q_sm)) if q_md else ""
        payload_t = ("**分位收益**\n\n" + tm_md + "\n\n" + interp_timing(s, tg.groupby(
            pd.qcut(tg["f"], 5, labels=False) + 1)["forward_5"].agg(["mean"]).reset_index()
            .rename(columns={"f": "group"}))) if tm_md else ""

        if args.dry:
            print("第%03d章 图%s IC%s 分层%s 择时%s"
                  % (s["ch"], "有" if fig else "无", "有" if ic_md else "无",
                     "有" if q_md else "无", "有" if tm_md else "无"))
            continue

        text = insert_after_section(text, "代码实现", payload_fig, "fig-indicator")
        text = insert_after_section(text, "截面选股能力", payload_ic + "\n\n" + payload_q, "tab-ic")
        text = insert_after_section(text, "择时能力", payload_t, "tab-timing")
        f.write_text(text, encoding="utf-8")
        del d, t, tg
        gc.collect()
        done += 1
        print("第%03d章 %-22s 图%s 表%s" % (s["ch"], s["name"],
                                           "✓" if fig else "−", "✓" if ic_md else "−"))
    print("\n完成 %d 章" % done)


if __name__ == "__main__":
    main()
