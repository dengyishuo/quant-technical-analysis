#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/staging/ 下的 CSV 转成 parquet，并派生书稿需要的研究面板。

输出（data/parquet/）：
  daily_prices.parquet   原始日线，一行一个标的日
  industry.parquet       行业与市值快照
  universe.parquet       扩展股票池
  index_daily.parquet    指数与 ETF
  panel.parquet          研究面板：已算好前向收益、波动率、可交易性标记

用法：python3 scripts/csv_to_parquet.py
"""

from __future__ import annotations

import sys
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAGING = ROOT / "data" / "staging"
OUT = ROOT / "data" / "parquet"

# A 股涨跌停：主板 10%，创业板与科创板 20%
LIMIT_MAIN = 0.098
LIMIT_GEM = 0.198


def read(name: str) -> pd.DataFrame | None:
    p = STAGING / name
    if not p.exists():
        print("  跳过（缺失）:", name)
        return None
    return pd.read_csv(p)


def board_of(code: str) -> str:
    """按代码前缀判断板块。"""
    c = code.split(".")[0]
    if c.startswith(("300", "301")):
        return "gem"       # 创业板 20%
    if c.startswith(("688", "689")):
        return "star"      # 科创板 20%
    if c.startswith(("8", "4")):
        return "bse"       # 北交所 30%
    return "main"          # 主板 10%


def repair_corporate_actions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """修补送股与转增造成的价格跳空。

    数据源的 adjusted 字段只做了现金分红（除息）复权，未做送转（除权）复权。
    表现为除权日开盘价直接低于前一日最低价，单日收益出现 -30% 这类不可能的值。

    修法：把开盘价与前一日收盘价的比例当作复权系数，向后累乘放大价格，
    使序列收益连续。假设隔夜无真实跳空（A 股为集合竞价，该假设近似成立），
    代价是除权当日的真实涨跌被并入复权系数，误差限于当日。

    返回修补后的数据框与被标记的除权日清单。
    """
    df = df.sort_values(["code", "date"]).copy()
    g = df.groupby("code", sort=False)

    prev_close = g["close"].shift(1)
    prev_vol = g["volume"].shift(1).fillna(0)

    # 开盘价低于前一日收盘价 15% 以上，且前一日有成交（排除停牌复牌）
    gap = df["open"] / prev_close - 1
    suspect = (gap < -0.15) & (prev_vol > 0) & prev_close.notna()

    df["corp_action"] = suspect.astype("int8")

    # 逐标的累乘复权系数：除权日的 k = 前收 / 开盘
    k = pd.Series(1.0, index=df.index)
    k[suspect] = (prev_close[suspect] / df.loc[suspect, "open"]).clip(1.0, 3.0)
    df["adj_mult"] = k.groupby(df["code"]).cumprod()

    for c in ["open", "high", "low", "close", "adjusted"]:
        df[c + "_raw"] = df[c]
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c] * df["adj_mult"]

    # 复权后的价格序列重新给出 adjusted
    df["adjusted"] = df["adjusted"] * df["adj_mult"]

    flagged = df.loc[suspect, ["date", "code", "open_raw", "close_raw",
                               "adj_mult"]].copy()
    return df, flagged


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # ---------- 1. 行情 ----------
    print("== 行情 ==")
    px = read("prices.csv")
    if px is None:
        sys.exit("缺少 prices.csv，请先运行 scripts/export_from_db.R")

    px["date"] = pd.to_datetime(px["date"])
    px["code"] = px["code"].astype(str)
    px = px.sort_values(["code", "date"]).reset_index(drop=True)

    # 类型收紧，parquet 体积小很多
    for c in ["open", "high", "low", "close", "adjusted", "volume"]:
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px["volume"] = px["volume"].fillna(0).astype("int64")

    px.to_parquet(OUT / "daily_prices.parquet", index=False, compression="snappy")
    print("  daily_prices.parquet  %d 行 × %d 列，%d 个标的"
          % (len(px), px.shape[1], px["code"].nunique()))

    # ---------- 2. 行业 ----------
    print("\n== 行业 ==")
    ind = read("industry_snapshot.csv")
    if ind is not None:
        ind["trade_date"] = pd.to_datetime(ind["trade_date"])
        ind["code"] = ind["code"].astype(str)
        ind.to_parquet(OUT / "industry.parquet", index=False, compression="snappy")
        print("  industry.parquet  %d 行，%d 个行业"
              % (len(ind), ind["industry"].nunique()))

    uni = read("universe.csv")
    if uni is not None:
        uni["code"] = uni["code"].astype(str)
        uni.to_parquet(OUT / "universe.parquet", index=False, compression="snappy")
        print("  universe.parquet  %d 只" % len(uni))

    # ---------- 3. 指数 ----------
    print("\n== 指数 ==")
    idx = read("index.csv")
    if idx is not None:
        idx["date"] = pd.to_datetime(idx["date"])
        idx["code"] = idx["code"].astype(str)
        for c in ["open", "high", "low", "close", "adjusted", "volume"]:
            idx[c] = pd.to_numeric(idx[c], errors="coerce")
        idx = idx.sort_values(["code", "date"]).reset_index(drop=True)
        idx.to_parquet(OUT / "index_daily.parquet", index=False, compression="snappy")
        print("  index_daily.parquet  %d 行，%d 个指数"
              % (len(idx), idx["code"].nunique()))

    # ---------- 4. 研究面板 ----------
    print("\n== 研究面板 ==")

    # 先修补送转除权，再算收益
    px, flagged = repair_corporate_actions(px)
    print("  除权修补：标记 %d 个除权日，涉及 %d 只标的"
          % (len(flagged), flagged["code"].nunique()))
    if len(flagged):
        flagged.to_parquet(OUT / "corp_action_flagged.parquet", index=False,
                           compression="snappy")

    df = px.copy()

    # 用复权价算收益，用原始价算指标（正文口径）
    df["adj"] = df["adjusted"].where(df["adjusted"].notna(), df["close"])
    g = df.groupby("code", sort=False)

    df["ret"] = g["adj"].pct_change()
    df["forward_1"] = g["adj"].shift(-1) / df["adj"] - 1
    df["forward_5"] = g["adj"].shift(-5) / df["adj"] - 1
    df["forward_20"] = g["adj"].shift(-20) / df["adj"] - 1

    # 未来 20 日已实现波动率（年化），供波动率类指标的检验目标
    fwd_ret = df["ret"].groupby(df["code"]).shift(-1)
    df["fwd_vol_20"] = (
        fwd_ret.groupby(df["code"])
        .transform(lambda s: s.rolling(20).std().shift(-19))
        * np.sqrt(252)
    )

    # 可交易性：涨跌停与停牌
    df["board"] = df["code"].map(board_of)
    thr = df["board"].map({"main": LIMIT_MAIN, "gem": LIMIT_GEM,
                           "star": LIMIT_GEM, "bse": 0.298}).fillna(LIMIT_MAIN)
    df["limit_up"] = (df["ret"] > thr).astype("int8")
    df["limit_down"] = (df["ret"] < -thr).astype("int8")
    df["suspended"] = (df["volume"] <= 0).astype("int8")

    # 价格有效性：停牌日的价格是前值填充，不是真实成交价
    df["price_valid"] = (df["volume"] > 0).astype("int8")

    # 复牌日：前一日停牌、当日恢复交易，首日通常不设涨跌幅
    prev_susp = df.groupby("code", sort=False)["suspended"].shift(1)
    df["resume_day"] = ((prev_susp == 1) & (df["suspended"] == 0)).fillna(False).astype("int8")

    # 次新股：数据集内的首日明显晚于窗口起点，且上市未满 250 个交易日。
    # 用首日是否等于窗口起点来排除"窗口开始前就已上市"的老股。
    start = df["date"].min()
    first = df.groupby("code", sort=False)["date"].transform("min")
    late_start = first > start + pd.Timedelta(days=30)
    young = (df["date"] - first) < pd.Timedelta(days=365)
    df["new_listing"] = (late_start & young).astype("int8")

    df["tradable"] = ((df["limit_up"] == 0) & (df["limit_down"] == 0)
                      & (df["suspended"] == 0)).astype("int8")

    # 行业并入
    if ind is not None:
        m = ind[["code", "name", "industry"]].drop_duplicates("code")
        df = df.merge(m, on="code", how="left")

    keep = ["date", "code", "name", "industry", "board",
            "open", "high", "low", "close", "adjusted", "volume",
            "open_raw", "high_raw", "low_raw", "close_raw",
            "ret", "forward_1", "forward_5", "forward_20", "fwd_vol_20",
            "corp_action", "resume_day", "new_listing",
            "limit_up", "limit_down", "suspended", "price_valid", "tradable"]
    df = df[[c for c in keep if c in df.columns]]
    df.to_parquet(OUT / "panel.parquet", index=False, compression="snappy")

    print("  panel.parquet  %d 行 × %d 列，%d 个标的"
          % (len(df), df.shape[1], df["code"].nunique()))
    print("    日期范围 %s 至 %s"
          % (df["date"].min().date(), df["date"].max().date()))
    print("    有行业分类 %.1f%%，可交易日占比 %.1f%%"
          % (df["industry"].notna().mean() * 100, df["tradable"].mean() * 100))

    # ---------- 5. 示例子集 ----------
    blue = ["600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ"]
    sub = df[df["code"].isin(blue) & (df["date"] >= "2023-01-01")
             & (df["date"] <= "2025-06-01")]
    sub.to_parquet(OUT / "panel_blue_chip.parquet", index=False, compression="snappy")
    print("\n  panel_blue_chip.parquet  %d 行，%d 个标的"
          % (len(sub), sub["code"].nunique()))

    # ---------- 6. 体积 ----------
    print("\n== 产出 ==")
    total = 0
    for f in sorted(OUT.glob("*.parquet")):
        kb = f.stat().st_size / 1024
        total += kb
        print("  %-28s %8.1f KB" % (f.name, kb))
    print("  %-28s %8.1f KB" % ("合计", total))


if __name__ == "__main__":
    main()
