# ============================================================
# Python 示例数据准备（5 只 A 股蓝筹面板，含因子与未来收益列）
#
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿（模块02-因子检验方法/第007章），再重新运行提取脚本。
# ============================================================
import pandas as pd

# 本地数据，由 xquant-db 导出，字段见 data/README.md
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
CODES = {"600519.SS": "贵州茅台", "600036.SS": "招商银行",
         "601318.SS": "中国平安", "300750.SZ": "宁德时代",
         "000858.SZ": "五粮液"}

frames = []
for code in CODES:
    _oneday = _panel[_panel["code"] == code].set_index("date").sort_index()
    raw = _oneday[["open", "high", "low", "close", "volume"]].copy()
    raw.columns = ["Open", "High", "Low", "Close", "Volume"]
    if raw.empty:
        continue
    d = raw["Close"].squeeze().to_frame("close")
    d["code"] = code
    d["sma20"] = d["close"].rolling(20).mean()
    d["sma_dev"] = d["close"] / d["sma20"] - 1
    d["forward_1"] = d["close"].pct_change().shift(-1)
    frames.append(d.reset_index().rename(columns={"Date": "date"}))

panel = pd.concat(frames, ignore_index=True)
ic = cross_section_ic(panel, "sma_dev", "forward_1")
print(ic_summary(ic))
