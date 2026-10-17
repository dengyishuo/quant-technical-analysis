# ============================================================
# 第048章 端到端案例：从指标到可交易信号
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第048章-端到端案例：从指标到可交易信号.md
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
#
# 依赖：先加载同目录下的公共函数与数据准备
#   exec(open("code/python/00-common.py").read())
#   exec(open("code/python/00-data.py").read())
#
# ------------------------------------------------------------

# ---- 代码块 1：第一步：特征构建 ----

import numpy as np
import pandas as pd

# 本地数据，由 xquant-db 导出，字段见 data/README.md
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
CODES = {"600519.SS": "贵州茅台", "600036.SS": "招商银行",
         "601318.SS": "中国平安", "300750.SZ": "宁德时代",
         "000858.SZ": "五粮液"}

def build_features(code):
    _oneday = _panel[_panel["code"] == code].set_index("date").sort_index()
    raw = _oneday[["open", "high", "low", "close", "volume"]].copy()
    raw.columns = ["Open", "High", "Low", "Close", "Volume"]
    if raw.empty:
        return None
    d = raw.squeeze()[["Open", "High", "Low", "Close", "Volume"]].copy()
    d.columns = ["open", "high", "low", "close", "volume"]
    d["code"] = code
    c, h, l, v = d["close"], d["high"], d["low"], d["volume"]

    # 趋势：价格相对二十日均线的偏离度
    d["sma_dev"] = c / c.rolling(20).mean() - 1
    # 趋势：MACD 柱状值归一
    dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    d["macd_bar"] = (dif - dea) / c
    # 趋势：ADX 强度值（简化实现）
    up, dn = h.diff(), -l.diff()
    dmp = np.where((up > dn) & (up > 0), up, 0)
    dmn = np.where((dn > up) & (dn > 0), dn, 0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    dmp = pd.Series(dmp, index=d.index).ewm(alpha=1/14, adjust=False).mean()
    dmn = pd.Series(dmn, index=d.index).ewm(alpha=1/14, adjust=False).mean()
    trs = tr.ewm(alpha=1/14, adjust=False).mean()
    di_diff = 100 * (dmp - dmn) / trs
    d["adx"] = di_diff.abs().ewm(alpha=1/14, adjust=False).mean()
    # 震荡：RSI 相对中轴的偏离
    gain = c.diff().clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-c.diff().clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    d["rsi_dev"] = (100 - 100 / (1 + gain / loss)) - 50
    # 震荡：随机指标 K 减 D
    ll, hh = l.rolling(9).min(), h.rolling(9).max()
    rsv = (c - ll) / (hh - ll + 1e-9) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    dd = k.ewm(com=2, adjust=False).mean()
    d["kd_diff"] = (k - dd) / 100
    # 波动率：真实波幅占价格比率的历史分位
    d["atr_ratio"] = tr.ewm(alpha=1/14, adjust=False).mean() / c
    d["atr_rank"] = d["atr_ratio"].rolling(120, min_periods=40).apply(
        lambda x: (x[-1] > x).mean(), raw=True)
    # 波动率：布林带带宽
    ma20, sd20 = c.rolling(20).mean(), c.rolling(20).std()
    d["bb_width"] = (4 * sd20) / ma20
    # 量价：OBV 的十日变化率
    sign = np.sign(c.diff().fillna(0))
    obv = (sign * v).cumsum()
    d["obv_change"] = obv.diff(10) / obv.shift(10).abs().replace(0, np.nan)
    # 标签：未来五日收益
    d["forward_5"] = c.pct_change().shift(-5)
    return d.reset_index().rename(columns={"Date": "date"})

frames = [f for f in (build_features(k) for k in CODES) if f is not None]
panel = pd.concat(frames, ignore_index=True)

FEATURES = ["sma_dev", "macd_bar", "adx", "rsi_dev",
            "kd_diff", "atr_rank", "bb_width", "obv_change"]
print("面板维度", panel.shape)
print("特征缺失率")
print(panel[FEATURES].isna().mean().round(3))

# ---- 代码块 2：第二步：特征预处理与横截面标准化 ----

def winsorize_z(s):
    """逐日横截面标准化（中位数与 MAD），再截断到正负三。"""
    med = s.median()
    mad = (s - med).abs().median()
    z = (s - med) / mad if mad > 0 else s * 0.0
    return z.clip(-3, 3)

# 逐日横截面标准化，得到入模特征
for feat in FEATURES:
    panel[feat + "_z"] = panel.groupby("date")[feat].transform(winsorize_z)

ZFEATURES = [f + "_z" for f in FEATURES]

# 标签：逐日横截面标准化的未来五日收益，作为回归目标
def cs_std(g):
    med = g.median()
    mad = (g - med).abs().median()
    return (g - med) / mad if mad > 0 else g * 0.0

panel["y"] = panel.groupby("date")["forward_5"].transform(cs_std)
panel = panel.dropna(subset=ZFEATURES + ["y"])
print("可用样本", len(panel))

# ---- 代码块 3：第三步：标签构造 ----

# 同时保留一个排名版本，便于与标准分版本对照
panel["y_rank"] = panel.groupby("date")["forward_5"].transform(
    lambda s: s.rank(pct=True) - 0.5)
print("标签标准差", round(panel["y"].std(), 3),
      "排名标签取值范围", (round(panel["y_rank"].min(), 2),
                          round(panel["y_rank"].max(), 2)))

# ---- 代码块 4：第四步：数据切分 ----

TRAIN_END = pd.Timestamp("2024-05-31")
VALID_START = pd.Timestamp("2024-06-11")     # 训练末日后留十天
VALID_END = pd.Timestamp("2024-12-31")
TEST_START = pd.Timestamp("2025-01-11")      # 验证末日后留十天

train = panel[panel["date"] <= TRAIN_END]
valid = panel[(panel["date"] >= VALID_START) & (panel["date"] <= VALID_END)]
test = panel[panel["date"] >= TEST_START]
print("训练", train["date"].min(), train["date"].max(), len(train))
print("验证", valid["date"].min(), valid["date"].max(), len(valid))
print("测试", test["date"].min(), test["date"].max(), len(test))

# ---- 代码块 5：第五步：单因子基线 ----

from scipy import stats

def cross_section_ic(panel, factor_col, ret_col, date_col="date"):
    """沿用第 007 章的横截面 IC 序列。"""
    def _ic(g):
        s = g.dropna(subset=[factor_col, ret_col])
        return stats.spearmanr(s[factor_col], s[ret_col])[0] if len(s) >= 5 else np.nan
    return panel.groupby(date_col).apply(_ic).dropna()

def ic_summary(ic):
    """沿用第 007 章的 IC 汇总。"""
    m, s = ic.mean(), ic.std()
    return pd.Series({"IC均值": round(m, 4), "IC标准差": round(s, 4),
                      "ICIR": round(m / s, 3) if s > 0 else np.nan,
                      "IC大于零比例": round((ic > 0).mean(), 3), "期数": len(ic)})

baseline = pd.DataFrame({f: ic_summary(cross_section_ic(train, f + "_z", "forward_5"))
                         for f in FEATURES}).T
print(baseline)

# ---- 代码块 6：第六步：树模型 ----

import lightgbm as lgb

model_gb = lgb.LGBMRegressor(
    n_estimators=1000,
    learning_rate=0.03,        # 小学习率，配合早停
    num_leaves=15,             # 限制复杂度
    max_depth=4,               # 限制交互阶数
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.6,
    min_child_samples=200,     # 叶子样本下限，金融场景设大
    reg_lambda=5.0,
    reg_alpha=0.5,
    random_state=0)

model_gb.fit(train[ZFEATURES], train["y"],
             eval_set=[(valid[ZFEATURES], valid["y"])],
             eval_metric="l2",
             callbacks=[lgb.early_stopping(50, verbose=False)])

imp = pd.Series(model_gb.booster_.feature_importance("gain"),
                index=ZFEATURES).sort_values(ascending=False)
print("gain 重要性")
print(imp.round(1))

# ---- 代码块 7：第六步：树模型 ----

def block_permutation_importance(model, X, y, block=20, n_repeat=5, seed=0):
    """分块排列重要性：在时间块之间置换，保留块内时序结构。"""
    rng = np.random.default_rng(seed)
    base = -np.mean((model.predict(X) - y) ** 2)
    idx = np.arange(len(X))
    blocks = np.array_split(idx, max(1, len(X) // block))
    out = {}
    for c in X.columns:
        drops = []
        for _ in range(n_repeat):
            Xp = X.copy()
            order = rng.permutation(len(blocks))
            new_idx = np.concatenate([blocks[p] for p in order])
            Xp[c] = Xp[c].to_numpy()[new_idx]
            drops.append(base - (-np.mean((model.predict(Xp) - y) ** 2)))
        out[c] = float(np.mean(drops))
    return pd.Series(out).sort_values(ascending=False)

perm = block_permutation_importance(model_gb, valid[ZFEATURES], valid["y"])
print("分块排列重要性")
print(perm.round(4))

# ---- 代码块 8：第六步：树模型 ----

valid_gb = valid.assign(gb=model_gb.predict(valid[ZFEATURES]))
print("树模型验证期", ic_summary(cross_section_ic(valid_gb, "gb", "forward_5")).to_dict())

# ---- 代码块 9：第七步：序列模型 ----

import torch
import torch.nn as nn

T = 20          # 回看窗口
STRIDE = 1      # 步长

def make_sequences(df, features, target, T, stride=1):
    """把面板切成 [N, T, F] 张量与标签，窗口不含未来。"""
    Xs, ys, dates, codes = [], [], [], []
    for code, g in df.groupby("code"):
        g = g.sort_values("date").reset_index(drop=True)
        X = g[features].to_numpy(dtype=np.float32)
        y = g[target].to_numpy(dtype=np.float32)
        dd = g["date"].to_numpy()
        for end in range(T, len(g), stride):
            win = X[end - T:end]
            if np.isnan(win).any() or np.isnan(y[end]):
                continue
            Xs.append(win); ys.append(y[end])
            dates.append(dd[end]); codes.append(code)
    return (np.stack(Xs), np.array(ys, dtype=np.float32),
            np.array(dates), np.array(codes))

# 窗口在训练期内构造，避免跨越切分边界
trX, trY, trD, trC = make_sequences(train, ZFEATURES, "y", T, STRIDE)
vaX, vaY, vaD, vaC = make_sequences(valid, ZFEATURES, "y", T, STRIDE)

# 标准化统计量只用训练窗口
mu = trX.reshape(-1, trX.shape[-1]).mean(axis=0)
sd = trX.reshape(-1, trX.shape[-1]).std(axis=0) + 1e-8
trX = (trX - mu) / sd
vaX = (vaX - mu) / sd
print("训练窗口", trX.shape, "验证窗口", vaX.shape)

# ---- 代码块 10：第七步：序列模型 ----

class LSTMRegressor(nn.Module):
    def __init__(self, n_features, hidden=16, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(self.drop(out[:, -1, :])).squeeze(-1)

torch.manual_seed(0)
model_lstm = LSTMRegressor(n_features=len(ZFEATURES))
opt = torch.optim.Adam(model_lstm.parameters(), lr=1e-3)
loss_fn = nn.MSELoss()

trX_t, trY_t = torch.tensor(trX), torch.tensor(trY)
vaX_t, vaY_t = torch.tensor(vaX), torch.tensor(vaY)

best, wait, tr_hist, va_hist = np.inf, 10, [], []
for epoch in range(200):
    model_lstm.train(); opt.zero_grad()
    loss = loss_fn(model_lstm(trX_t), trY_t)
    loss.backward(); opt.step()
    model_lstm.eval()
    with torch.no_grad():
        va_loss = loss_fn(model_lstm(vaX_t), vaY_t).item()
    tr_hist.append(loss.item()); va_hist.append(va_loss)
    if va_loss < best - 1e-6:
        best, wait = va_loss, 0
        torch.save(model_lstm.state_dict(), "lstm_best.pt")
    else:
        wait += 1
        if wait >= 10:
            break
print("最佳验证损失", round(best, 5))

# ---- 代码块 11：第七步：序列模型 ----

model_lstm.load_state_dict(torch.load("lstm_best.pt"))
model_lstm.eval()
with torch.no_grad():
    lstm_score = model_lstm(vaX_t).numpy()

valid_lstm = pd.DataFrame({"date": vaD, "code": vaC, "lstm": lstm_score})
valid_lstm = valid_lstm.merge(valid[["date", "code", "forward_5"]], on=["date", "code"])
print("序列模型验证期",
      ic_summary(cross_section_ic(valid_lstm, "lstm", "forward_5")).to_dict())

# ---- 代码块 12：第八步：融合 ----

from sklearn.linear_model import Ridge

def cs_rank(g):
    return g.rank(pct=True)

# 用验证期的基模型输出作为示意：真实流程需在训练期用扩张窗口生成 OOF 预测
fuse = valid.assign(
    gb=model_gb.predict(valid[ZFEATURES])).copy()

# 序列模型输出与表格数据按 date/code 对齐
fuse = fuse.merge(valid_lstm[["date", "code", "lstm"]], on=["date", "code"], how="left")
for c in ["gb", "lstm"]:
    fuse[c + "_q"] = fuse.groupby("date")[c].transform(cs_rank)

QCOLS = ["gb_q", "lstm_q"]
# 逐个加入基模型，观察合成的边际贡献
steps = [["gb_q"], ["gb_q", "lstm_q"]]
for cols in steps:
    sub = fuse.dropna(subset=cols + ["y"])
    m = Ridge(alpha=1.0).fit(sub[cols], sub["y"])
    sub = sub.assign(fused=m.predict(sub[cols]))
    print(cols, ic_summary(cross_section_ic(sub, "fused", "y")).to_dict(),
          "系数", dict(zip(cols, m.coef_.round(3))))

# ---- 代码块 13：第八步：融合 ----

# 单因子等权：八个方向对齐后的标准化特征平均
fuse["equal"] = fuse[ZFEATURES].mean(axis=1)

def layered_returns(panel, factor_col, ret_col, q=5, date_col="date"):
    def _assign(g):
        g = g.dropna(subset=[factor_col, ret_col]).copy()
        if len(g) < q:
            return None
        g["group"] = pd.qcut(g[factor_col].rank(method="first"), q, labels=False) + 1
        return g
    tmp = panel.groupby(date_col, group_keys=False).apply(_assign).dropna(subset=["group"])
    grp = tmp.groupby(["date", "group"])[ret_col].mean().unstack()
    gm = grp.mean()
    mono, _ = stats.spearmanr(gm.index.values, gm.values)
    return gm.round(5), round(mono, 3)

for col in ["equal", "gb", "fused"]:
    print(col, ic_summary(cross_section_ic(fuse, col, "y")).to_dict())
print("融合信号分层回测", layered_returns(fuse, "fused", "forward_5"))

# ---- 代码块 14：第九步：回测与成本 ----

def backtest_ls(panel, factor_col, ret_col, date_col="date", q=3,
                fee=0.0003, stamp=0.001, rebalance="ME"):
    """多空组合回测，按月调仓，计入费率与印花税。"""
    df = panel.dropna(subset=[factor_col, ret_col]).copy()
    df["period"] = pd.to_datetime(df[date_col]).dt.to_period("M")

    prev_long, prev_short = set(), set()
    rows = []
    for p, g in df.groupby("period"):
        g = g.copy()
        g["grp"] = pd.qcut(g[factor_col].rank(method="first"), q, labels=False) + 1
        long = g[g["grp"] == q]
        short = g[g["grp"] == 1]
        long_set = set(long["code"])
        short_set = set(short["code"])
        gross = long[ret_col].mean() - short[ret_col].mean()
        # 单边换手：本次持仓相对上期的差异比例，多空各算一次
        def turnover(now, prev):
            if not prev:
                return 1.0
            return 1 - len(now & prev) / max(len(now), 1)
        turn = turnover(long_set, prev_long) + turnover(short_set, prev_short)
        # 成本近似：单边换手之和乘以单边成本，费率双边计，印花税按卖出计
        cost = turn * (fee + stamp)
        rows.append({"period": p, "gross": gross, "turnover": turn, "net": gross - cost})
        prev_long, prev_short = long_set, short_set

    out = pd.DataFrame(rows)
    ann = (1 + out["net"]).prod() ** (12 / len(out)) - 1
    sharpe = out["net"].mean() / out["net"].std() * np.sqrt(12) if out["net"].std() > 0 else np.nan
    return out, round(ann, 4), round(sharpe, 2)

out, ann, sharpe = backtest_ls(fuse, "fused", "forward_5")
print("平均单边换手", round(out["turnover"].mean(), 3),
      "平均毛收益", round(out["gross"].mean(), 4),
      "平均净收益", round(out["net"].mean(), 4))

# ---- 代码块 15：第九步：回测与成本 ----

# 简化的可交易性过滤示意：按涨跌幅识别可能难以成交的时点
def tradable_mask(df, limit=0.098):
    """标记可能非可交易的样本：收盘价接近涨跌停。"""
    c = df["close"]
    up_limit = c.pct_change() >= limit
    dn_limit = c.pct_change() <= -limit
    return ~(up_limit | dn_limit)

fuse["tradable"] = tradable_mask(fuse)
print("可交易样本占比", round(fuse["tradable"].mean(), 3))

# ---- 代码块 16：第十一步：上线与监控 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

def rolling_ic_curve(panel, factor_col, ret_col="forward_5", window=60):
    ic = cross_section_ic(panel, factor_col, ret_col)
    roll = ic.rolling(window, min_periods=20).mean()
    return roll

roll = rolling_ic_curve(fuse, "fused")
fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(range(len(roll)), roll.values, label="滚动 IC 均值")
ax.axhline(0, color="gray", linewidth=1)
ax.axhline(roll.quantile(0.1), color="red", linestyle="--", label="历史 10% 分位")
ax.set_title("融合信号滚动样本外 IC（示意）")
ax.set_xlabel("期数")
ax.legend()
plt.tight_layout()
plt.show()
