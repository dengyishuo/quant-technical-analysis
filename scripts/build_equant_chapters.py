#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 equant_spec.py 重写 28 个指标章的计算代码，改用 eQuant 生态。

Python 侧：ettr 算指标、efactorcraft 做检验、efincharts 画图。
R 侧：ettr 的 add_* 系列、efactorcraft 的 ic_analysis 系列、efincharts 的 ecandlesticks。

替换范围：每个指标章的 6 个代码块（代码实现 / 拆解 / 截面 / 择时 / 组合×2），
R 与 Python 各一份。正文其余部分不动。

用法：python3 scripts/build_equant_chapters.py [--dry]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from equant_spec import SPEC

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 图与表的输出目录
FIG = "assets/figures"

# ────────────────────────── Python 模板 ──────────────────────────

PY_PREREQ = '''import pandas as pd
import ettr
import efactorcraft as efc
import efincharts as efc_

# 中文字体：mplfinance 会用 style 里的 rc 覆盖全局设置，必须写进 style
from efincharts import theme
theme.efin_style["rc"] = {
    "font.sans-serif": ["PingFang SC", "Heiti SC", "SimHei"],
    "axes.unicode_minus": False,
    "font.family": "sans-serif",
}

# 本地数据由 xquant-db 导出，字段见 data/README.md
blue = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
panel = pd.read_parquet("data/parquet/panel.parquet")
panel = panel[(panel["date"] >= "2023-01-01") & (panel["date"] <= "2025-06-01")]


def one(df, code="600519.SS"):
    """取单只标的，转成 efincharts 需要的宽表。"""
    x = df[df["code"] == code].sort_values("date").set_index("date")
    x.columns = [c.capitalize() for c in x.columns]
    return x
'''


def py_call(fn: str, kw: dict) -> str:
    if not kw:
        return "ettr.%s(d)" % fn
    args = ", ".join("%s=%r" % (k, v) for k, v in kw.items())
    return "ettr.%s(d, %s)" % (fn, args)


def py_indicator_block(s: dict) -> str:
    lines = [PY_PREREQ, "# 1. 取单只标的", "maotai = blue[blue['code'] == '600519.SS'].copy()", ""]
    lines.append("# 2. ettr 在长格式面板上追加指标列，不需要手工 rolling")
    calls = "\n".join("maotai = ettr.%s(maotai%s)" % (
        fn, (", " + ", ".join("%s=%r" % (k, v) for k, v in kw.items())) if kw else "")
        for fn, kw in s["py"])
    lines.append(calls)
    lines.append("")
    lines.append("cols = [c for c in maotai.columns if c not in blue.columns]")
    lines.append("print(maotai[cols].describe().round(3))")
    lines.append("")
    lines.append("# 3. 画图：K 线 + 成交量 + 指标面板")
    lines.append('px = one(maotai)')
    lines.append('ch = efc_.candlestick(px, volume=True, title="贵州茅台 · %s")' % s["name"])
    lines.append('ch.save("%s/ch%03d/indicator.png")' % (FIG, s["ch"]))
    return "\n".join(lines)


def py_feature_block(s: dict) -> str:
    d = "d"
    col = s["py_col"]
    fac = s["factor"].format(c='d["%s"]' % col, d="d.")
    lines = [PY_PREREQ]
    pre = s.get("pre")
    body = []
    for fn, kw in s["py"]:
        body.append("d = " + py_call(fn, kw))
    lines.append("# 1. 先在面板上算原始指标")
    lines.append("d = panel.copy()")
    lines.extend(body)
    lines.append("")
    if pre == "py_dma":
        lines.append('d["DMA"] = d["SMA_10"] - d["SMA_50"]')
    elif pre == "py_bbi":
        lines.append('d["BBI"] = (d["SMA_3"] + d["SMA_6"] + d["SMA_12"] + d["SMA_24"]) / 4')
    elif pre == "py_macd":
        lines.append('# MACD 柱 = DIF - DEA，ettr 已算好')
        lines.append('d["MACD_hist"] = d["MACD_hist"]')
    elif pre == "py_vo":
        lines.append('d["VO"] = d["SMA_5"] / d["SMA_20"] - 1')
    lines.append("# 2. 转成无量纲因子，才能跨标的排序")
    if s.get("shift"):
        lines.append('d = d.sort_values(["code", "date"])')
        lines.append('d["f"] = d.groupby("code")["%s"].pct_change(10)' % col)
    else:
        lines.append('d["f"] = ' + fac)
    lines.append("")
    lines.append('print(d["f"].describe().round(4))')
    return "\n".join(lines)


def py_ic_block(s: dict) -> str:
    lines = [PY_PREREQ]
    if s["panel"] == "blue":
        lines.append("# 5 只标的的横截面只有 5 个样本，只能演示流程")
        lines.append("src = blue.copy()")
    else:
        lines.append("# 287 只、2023-01 至 2025-06，横截面才有统计意义")
        lines.append("src = panel.copy()")
    lines.append("d = src.copy()")
    lines.append("")
    lines.append("# 1. 算指标")
    body = []
    for fn, kw in s["py"]:
        body.append("d = " + py_call(fn, kw))
    lines.append("\n".join(body))
    lines.append("")
    pre = s.get("pre")
    col = s["py_col"]
    if pre == "py_dma":
        lines.append('d["DMA"] = d["SMA_10"] - d["SMA_50"]')
    elif pre == "py_bbi":
        lines.append('d["BBI"] = (d["SMA_3"] + d["SMA_6"] + d["SMA_12"] + d["SMA_24"]) / 4')
    elif pre == "py_vo":
        lines.append('d["VO"] = d["SMA_5"] / d["SMA_20"] - 1')
    lines.append("")
    lines.append("# 2. 因子 + 未来收益")
    if s.get("shift"):
        lines.append('d = d.sort_values(["code", "date"])')
        lines.append('d["f"] = d.groupby("code")["%s"].pct_change(10)' % col)
    else:
        lines.append('d["f"] = ' + s["factor"].format(c='d["%s"]' % col, d="d."))
    lines.append("d = efc.add_next_return(d, periods=(1, 5, 20))")
    lines.append("")
    lines.append("# 3. 截面 IC 与分层")
    lines.append('ic = efc.ic_analysis(d, factor_cols="f",')
    lines.append('                      forward_cols=["forward_1", "forward_5", "forward_20"],')
    lines.append('                      method="spearman")')
    lines.append("print(efc.ir_analysis(ic).round(3))")
    lines.append("")
    lines.append('q = efc.quantile_analysis(d, factor_col="f", forward_col="forward_5", n_groups=5)')
    lines.append('print(q["summary"].round(4))')
    return "\n".join(lines)


def py_timing_block(s: dict) -> str:
    col = s["py_col"]
    lines = [PY_PREREQ]
    lines.append('# 择时检验用 ETF 做市场载体，指数本身没有日线数据')
    lines.append('idx = pd.read_parquet("data/parquet/index_daily.parquet")')
    lines.append('idx = idx[idx["code"] == "510300.SS"].sort_values("date")')
    lines.append("t = idx.copy()")
    lines.append("")
    lines.append("# 1. 在 ETF 上算同一个指标")
    body = []
    for fn, kw in s["py"]:
        body.append("t = " + py_call(fn, kw))
    lines.append("\n".join(body))
    lines.append("")
    pre = s.get("pre")
    if pre == "py_dma":
        lines.append('t["DMA"] = t["SMA_10"] - t["SMA_50"]')
    elif pre == "py_bbi":
        lines.append('t["BBI"] = (t["SMA_3"] + t["SMA_6"] + t["SMA_12"] + t["SMA_24"]) / 4')
    elif pre == "py_vo":
        lines.append('t["VO"] = t["SMA_5"] / t["SMA_20"] - 1')
    lines.append("")
    lines.append("# 2. 按因子分位看未来 5 日收益")
    if s.get("shift"):
        lines.append('t["f"] = t["%s"].pct_change(10)' % col)
    else:
        lines.append('t["f"] = ' + s["factor"].format(c='t["%s"]' % col, d="t."))
    lines.append('t["forward_5"] = t["close"].shift(-5) / t["close"] - 1')
    lines.append('# 因子可能有重复值，先按名次切，避免 qcut 报边界不唯一')
    lines.append('t["q"] = pd.qcut(t["f"].rank(method="first"), 5, labels=False) + 1')
    lines.append('t = t.dropna(subset=["f", "forward_5"])')
    lines.append('print(t.groupby("q")["forward_5"].agg(["mean", "count"]).round(4))')
    return "\n".join(lines)


def py_combo_block(s: dict) -> str:
    lines = [PY_PREREQ]
    lines.append("d = panel.copy()")
    lines.append("")
    lines.append("# 1. 本章因子")
    body = []
    for fn, kw in s["py"]:
        body.append("d = " + py_call(fn, kw))
    lines.append("\n".join(body))
    pre = s.get("pre")
    col = s["py_col"]
    if pre == "py_dma":
        lines.append('d["DMA"] = d["SMA_10"] - d["SMA_50"]')
    elif pre == "py_bbi":
        lines.append('d["BBI"] = (d["SMA_3"] + d["SMA_6"] + d["SMA_12"] + d["SMA_24"]) / 4')
    elif pre == "py_vo":
        lines.append('d["VO"] = d["SMA_5"] / d["SMA_20"] - 1')
    if s.get("shift"):
        lines.append('d = d.sort_values(["code", "date"])')
        lines.append('d["f1"] = d.groupby("code")["%s"].pct_change(10)' % col)
    else:
        lines.append('d["f1"] = ' + s["factor"].format(c='d["%s"]' % col, d="d."))
    lines.append("")
    lines.append("# 2. 配一个量价因子做对照")
    lines.append('d = ettr.cmf(d, n=20)')
    lines.append('d["f2"] = d["CMF_20"]')
    lines.append("d = efc.add_next_return(d, periods=(5,))")
    lines.append("")
    lines.append("# 3. 单因子与等权组合的信息比率")
    lines.append('ic = efc.ic_analysis(d, factor_cols=["f1", "f2"], forward_cols=["forward_5"],')
    lines.append('                      method="spearman")')
    lines.append('d = efc.equal_weighted_composite(d, factor_cols=["f1", "f2"], new_col="f1_f2")')
    lines.append('ic2 = efc.ic_analysis(d, factor_cols=["f1_f2"], forward_cols=["forward_5"],')
    lines.append('                      method="spearman")')
    lines.append("ic.update(ic2)")
    lines.append("print(efc.ir_analysis(ic).round(3))")
    return "\n".join(lines)


# ────────────────────────── R 模板 ──────────────────────────

R_PREREQ = '''library(ettr)
library(efactorcraft)
library(efincharts)
library(ggplot2)

# 本地数据由 xquant-db 导出，字段见 data/README.md
# 同一章会多次用到这两份数据，这里读一次缓存起来，避免反复解压
.cache <- new.env(parent = emptyenv())
.blue <- function() {
  if (!exists("b", .cache)) {
    b <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
    b$date <- as.Date(b$date)
    assign("b", b, .cache)
  }
  get("b", .cache)
}
.panel <- function() {
  if (!exists("p", .cache)) {
    # 287 只的完整面板压成 gz，read.csv 支持 gz
    p <- read.csv("data/parquet/panel_r.csv.gz", stringsAsFactors = FALSE)
    p$date <- as.Date(p$date)
    p <- p[p$date >= "2023-01-01" & p$date <= "2025-06-01", ]
    assign("p", p, .cache)
  }
  get("p", .cache)
}
blue  <- .blue()
panel <- .panel()

# efincharts 要求 xts 且列名带 Adjusted
as_xts <- function(df) {
  x <- xts::xts(df[, c("open", "high", "low", "close", "volume", "adjusted")],
                order.by = df$date)
  colnames(x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
  x
}
'''


def r_calls(s: dict, var: str) -> str:
    out = []
    for fn, arg in s["r"]:
        if arg:
            out.append("%s <- %s(%s, %s)" % (var, fn, var, arg))
        else:
            out.append("%s <- %s(%s)" % (var, fn, var))
    return "\n".join(out)


def r_feature_expr(s: dict, var: str = "d") -> str:
    col = s["r_col"]
    fac = s["factor"].format(c='%s$`%s`' % (var, col), d="%s$" % var)
    return fac


def r_indicator_block(s: dict) -> str:
    lines = [R_PREREQ]
    lines.append('maotai <- .blue()[.blue()$code == "600519.SS", ]')
    lines.append("")
    lines.append("# 1. ettr 在长格式面板上追加指标列")
    lines.append(r_calls(s, "maotai"))
    lines.append("")
    lines.append("# 2. 基本统计")
    lines.append("cols <- setdiff(names(maotai), names(blue))")
    lines.append("print(summary(maotai[, cols]))")
    lines.append("")
    lines.append("# 3. K 线 + 成交量 + 均线")
    lines.append('ch <- ecandlesticks(as_xts(maotai), show_ma = TRUE, ma_periods = c(20, 60),')
    lines.append('                    title = "贵州茅台 · %s")' % s["name"])
    lines.append('ggsave("%s/ch%03d/indicator_r.png", ch$combined_plot,' % (FIG, s["ch"]))
    lines.append("       width = 10, height = 6, dpi = 110)")
    return "\n".join(lines)


def r_feature_block(s: dict) -> str:
    lines = [R_PREREQ]
    lines.append('d <- .blue()[.blue()$code == "600519.SS", ]')
    lines.append(r_calls(s, "d"))
    lines.append("")
    pre = s.get("pre")
    if pre == "py_dma":
        lines.append("d$DMA <- d$SMA_10 - d$SMA_50")
    elif pre == "py_bbi":
        lines.append("d$BBI <- (d$SMA_3 + d$SMA_6 + d$SMA_12 + d$SMA_24) / 4")
    elif pre == "py_vo":
        lines.append("d$VO <- d$SMA_5 / d$SMA_20 - 1")
    lines.append("# 转成无量纲因子")
    if s.get("shift"):
        lines.append('d$f <- c(rep(NA, 10), diff(log(d$%s), 10))' % s["r_col"])
    else:
        lines.append("d$f <- " + r_feature_expr(s))
    lines.append("")
    lines.append('print(summary(d$f))')
    return "\n".join(lines)


def r_ic_block(s: dict) -> str:
    lines = [R_PREREQ]
    lines.append("d <- .panel()")
    lines.append(r_calls(s, "d"))
    pre = s.get("pre")
    if pre == "py_dma":
        lines.append("d$DMA <- d$SMA_10 - d$SMA_50")
    elif pre == "py_bbi":
        lines.append("d$BBI <- (d$SMA_3 + d$SMA_6 + d$SMA_12 + d$SMA_24) / 4")
    elif pre == "py_vo":
        lines.append("d$VO <- d$SMA_5 / d$SMA_20 - 1")
    lines.append("")
    if s.get("shift"):
        lines.append("d <- d[order(d$code, d$date), ]")
        lines.append("d$f <- ave(d$%s, d$code, FUN = function(x)" % s["r_col"])
        lines.append("  c(rep(NA, 10), diff(log(x), 10)))")
    else:
        lines.append("d$f <- " + r_feature_expr(s))
    lines.append("d <- add_next_return(d, close_col = \"close\", n = c(1, 5, 20))")
    lines.append("")
    lines.append('ic <- ic_analysis(d, factor_cols = "f",')
    lines.append('                    forward_cols = c("forward_1", "forward_5", "forward_20"),')
    lines.append('                    method = "spearman")')
    lines.append("print(ir_analysis(ic))")
    lines.append("")
    lines.append('q <- quantile_analysis(d, factor_cols = "f", forward_cols = "forward_5",')
    lines.append("                       n_groups = 5)")
    lines.append("print(q$f$summary)")
    return "\n".join(lines)


def r_timing_block(s: dict) -> str:
    lines = [R_PREREQ]
    lines.append('idx <- read.csv("data/parquet/index_daily.csv", stringsAsFactors = FALSE)')
    lines.append("idx$date <- as.Date(idx$date)")
    lines.append('t <- idx[idx$code == "510300.SS", ]')
    lines.append(r_calls(s, "t"))
    pre = s.get("pre")
    if pre == "py_dma":
        lines.append("t$DMA <- t$SMA_10 - t$SMA_50")
    elif pre == "py_bbi":
        lines.append("t$BBI <- (t$SMA_3 + t$SMA_6 + t$SMA_12 + t$SMA_24) / 4")
    elif pre == "py_vo":
        lines.append("t$VO <- t$SMA_5 / t$SMA_20 - 1")
    if s.get("shift"):
        lines.append("t$f <- c(rep(NA, 10), diff(log(t$%s), 10))" % s["r_col"])
    else:
        lines.append("t$f <- " + r_feature_expr(s, "t"))
    lines.append("t$forward_5 <- c(tail(t$close, -5) / head(t$close, -5) - 1, rep(NA, 5))")
    lines.append("t$q <- cut(t$f, quantile(t$f, 0:5/5, na.rm = TRUE), include.lowest = TRUE, labels = FALSE)")
    lines.append("print(aggregate(forward_5 ~ q, data = t, FUN = function(x)")
    lines.append("  c(mean = mean(x, na.rm = TRUE), n = sum(!is.na(x)))))")
    return "\n".join(lines)


def r_combo_block(s: dict) -> str:
    lines = [R_PREREQ]
    lines.append("d <- .panel()")
    lines.append(r_calls(s, "d"))
    pre = s.get("pre")
    if pre == "py_dma":
        lines.append("d$DMA <- d$SMA_10 - d$SMA_50")
    elif pre == "py_bbi":
        lines.append("d$BBI <- (d$SMA_3 + d$SMA_6 + d$SMA_12 + d$SMA_24) / 4")
    elif pre == "py_vo":
        lines.append("d$VO <- d$SMA_5 / d$SMA_20 - 1")
    if s.get("shift"):
        lines.append("d <- d[order(d$code, d$date), ]")
        lines.append("d$f1 <- ave(d$%s, d$code, FUN = function(x)" % s["r_col"])
        lines.append("  c(rep(NA, 10), diff(log(x), 10)))")
    else:
        lines.append("d$f1 <- " + r_feature_expr(s))
    lines.append("d <- add_cmf(d, n = 20)")
    lines.append("d$f2 <- d$CMF")
    lines.append("d <- add_next_return(d, close_col = \"close\", n = 5)")
    lines.append('ic1 <- ic_analysis(d, factor_cols = c("f1", "f2"),')
    lines.append('                    forward_cols = "forward_5", method = "spearman")')
    lines.append("print(ir_analysis(ic1))")
    return "\n".join(lines)


# ────────────────────────── 替换 ──────────────────────────

BLOCK_RE = re.compile(r"^```(r|python)[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)


def rewrite(path: pathlib.Path, s: dict) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    blocks = list(BLOCK_RE.finditer(text))
    if len(blocks) != 12:
        print("  ! %s 有 %d 个代码块，预期 12，跳过" % (path.name, len(blocks)))
        return 0, 0

    # 按顺序分配：代码实现R, 代码实现Py, 拆解R, 拆解Py, 截面R, 截面Py,
    #             择时R, 择时Py, 组合R1, 组合R2, 组合Py1, 组合Py2
    plan = [
        ("r", r_indicator_block(s)),
        ("python", py_indicator_block(s)),
        ("r", r_feature_block(s)),
        ("python", py_feature_block(s)),
        ("r", r_ic_block(s)),
        ("python", py_ic_block(s)),
        ("r", r_timing_block(s)),
        ("python", py_timing_block(s)),
        ("r", r_combo_block(s)),
        ("r", r_combo_block(s)),
        ("python", py_combo_block(s)),
        ("python", py_combo_block(s)),
    ]

    out, last, n = [], 0, 0
    for m, (lang, code) in zip(blocks, plan):
        out.append(text[last:m.start()])
        out.append("```%s\n%s\n```" % (lang, code.rstrip("\n")))
        last = m.end()
        n += 1
    out.append(text[last:])
    path.write_text("".join(out), encoding="utf-8")
    return n, len(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    files = {int(re.match(r"第(\d+)章", f.name).group(1)): f
             for f in ROOT.glob("模块*/第*.md") if re.match(r"第(\d+)章", f.name)}

    total = 0
    for s in SPEC:
        f = files.get(s["ch"])
        if f is None:
            print("  ! 第%03d章 找不到文件" % s["ch"])
            continue
        if args.dry:
            print("第%03d章 %s  →  %s" % (s["ch"], s["name"], f.name))
            continue
        n, before = rewrite(f, s)
        total += n
        print("第%03d章 %-22s 替换 %d 块" % (s["ch"], s["name"], n))
    print()
    print("合计替换 %d 块" % total)


if __name__ == "__main__":
    main()
