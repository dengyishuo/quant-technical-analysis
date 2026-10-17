# ============================================================
# 第044章 序列模型：时间结构的建模
# 模块 08 机器学习挖掘与融合
# 源文件：模块08-机器学习挖掘与融合/第044章-序列模型：时间结构的建模.md
# ============================================================
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿，再重新运行提取脚本。
#
# 依赖：先加载同目录下的公共函数与数据准备
#   exec(open("code/python/00-common.py").read())
#   exec(open("code/python/00-data.py").read())
#
# ------------------------------------------------------------

# ---- 代码块 1：代码实现 ----

import numpy as np
import pandas as pd

# 本地数据，由 xquant-db 导出，字段见 data/README.md
_panel = pd.read_parquet("data/parquet/panel_blue_chip.parquet")
import torch
import torch.nn as nn

FEATURES = ["ret5", "ma20_dev", "vol20", "vol_ratio"]
T = 20        # 窗口长度：回看 20 个交易日
STRIDE = 1    # 步长：逐日滑动

def build_panel(codes):
    frames = []
    for code in codes:
        _oneday = _panel[_panel["code"] == code].set_index("date").sort_index()
        raw = _oneday[["open", "high", "low", "close", "volume"]].copy()
        raw.columns = ["Open", "High", "Low", "Close", "Volume"]
        if raw.empty:
            continue
        d = raw.squeeze()[["Close", "Volume"]].copy()
        d.columns = ["close", "volume"]
        d["code"] = code
        d["ret5"] = d["close"].pct_change(5)
        d["ma20_dev"] = d["close"] / d["close"].rolling(20).mean() - 1
        d["vol20"] = d["close"].pct_change().rolling(20).std()
        d["vol_ratio"] = d["volume"] / d["volume"].rolling(20).mean()
        # 目标：未来 5 日收益（收盘对收盘，仅在窗口末端之后）
        d["forward_5"] = d["close"].pct_change().shift(-5)
        frames.append(d.reset_index().rename(columns={"Date": "date"}))
    return pd.concat(frames, ignore_index=True)

def make_sequences(panel, features, target, T, stride=1):
    """把面板切成 [N, T, F] 张量与对应标签。每个窗口只使用末端及之前的数据。"""
    Xs, ys, dates, codes = [], [], [], []
    for code, g in panel.groupby("code"):
        g = g.sort_values("date").reset_index(drop=True)
        X = g[features].to_numpy(dtype=np.float32)
        y = g[target].to_numpy(dtype=np.float32)
        dd = g["date"].to_numpy()
        # 窗口覆盖 [end-T, end)，标签取 end 处的未来收益，因此窗口不含未来
        for end in range(T, len(g), stride):
            win = X[end - T:end]
            if np.isnan(win).any() or np.isnan(y[end]):
                continue
            Xs.append(win)
            ys.append(y[end])
            dates.append(dd[end])
            codes.append(code)
    return (np.stack(Xs), np.array(ys, dtype=np.float32),
            np.array(dates), np.array(codes))

# ---- 代码块 2：代码实现 ----

def split_with_buffer(X, y, dates, train_end, buffer_days):
    """按时间切分。缓冲期使验证窗口不与训练窗口在时间上重叠。"""
    train_end = np.datetime64(train_end)
    valid_start = train_end + np.timedelta64(buffer_days, "D")
    tr = dates <= train_end
    va = dates > valid_start
    return (X[tr], y[tr]), (X[va], y[va])

codes = ["600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ"]
panel = build_panel(codes).dropna(subset=FEATURES + ["forward_5"])
X, y, dates, gcodes = make_sequences(panel, FEATURES, "forward_5", T, STRIDE)
print("窗口总数", X.shape)

(trX, trY), (vaX, vaY) = split_with_buffer(X, y, dates, "2024-08-01", buffer_days=T + 20)

# 特征标准化只用训练集统计量，避免泄漏
mu = trX.reshape(-1, trX.shape[-1]).mean(axis=0)
sd = trX.reshape(-1, trX.shape[-1]).std(axis=0) + 1e-8
trX = (trX - mu) / sd
vaX = (vaX - mu) / sd
print("训练窗口", len(trX), "验证窗口", len(vaX))

# ---- 代码块 3：代码实现 ----

class LSTMRegressor(nn.Module):
    def __init__(self, n_features, hidden=16, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=1, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.lstm(x)          # out: [N, T, hidden]
        return self.head(self.drop(out[:, -1, :])).squeeze(-1)

torch.manual_seed(0)
model = LSTMRegressor(n_features=len(FEATURES))
opt = torch.optim.Adam(model.parameters(), lr=1e-3)
loss_fn = nn.MSELoss()

trX_t = torch.tensor(trX); trY_t = torch.tensor(trY)
vaX_t = torch.tensor(vaX); vaY_t = torch.tensor(vaY)

best_va, patience, wait = np.inf, 10, 0
tr_hist, va_hist = [], []
for epoch in range(200):
    model.train()
    opt.zero_grad()
    loss = loss_fn(model(trX_t), trY_t)     # 简化为全量批，仅演示
    loss.backward()
    opt.step()
    model.eval()
    with torch.no_grad():
        va_loss = loss_fn(model(vaX_t), vaY_t).item()
    tr_hist.append(loss.item()); va_hist.append(va_loss)
    if va_loss < best_va - 1e-6:
        best_va, wait = va_loss, 0
        torch.save(model.state_dict(), "lstm_best.pt")
    else:
        wait += 1
        if wait >= patience:                # 早停
            break
print("最佳验证损失", round(best_va, 5))

# ---- 代码块 4：代码实现 ----

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "SimHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(tr_hist, label="训练损失")
ax.plot(va_hist, label="验证损失")
ax.set_xlabel("轮次")
ax.set_ylabel("MSE")
ax.set_title("LSTM 训练过程（示意）")
ax.legend()
plt.tight_layout()
plt.show()

# ---- 代码块 5：代码实现 ----

class CausalConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch, kernel=3, dilation=1):
        super().__init__()
        self.pad = (kernel - 1) * dilation      # 只在左侧填充
        self.conv = nn.Conv1d(in_ch, out_ch, kernel, dilation=dilation)
        self.act = nn.ReLU()

    def forward(self, x):
        x = x.transpose(1, 2)                   # [N, T, C] -> [N, C, T]
        x = nn.functional.pad(x, (self.pad, 0)) # 左侧补零，右侧不补
        return self.act(self.conv(x)).transpose(1, 2)

class TCNRegressor(nn.Module):
    def __init__(self, n_features, hidden=16, dilations=(1, 2, 4)):
        super().__init__()
        layers, c = [], n_features
        for d in dilations:                     # 膨胀率成倍增长，扩大感受野
            layers.append(CausalConvBlock(c, hidden, kernel=3, dilation=d))
            c = hidden
        self.net = nn.Sequential(*layers)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        h = self.net(x)
        return self.head(h[:, -1, :]).squeeze(-1)

# ---- 代码块 6：代码实现 ----

import lightgbm as lgb

def window_stats(X):
    """把每个窗口压成少量统计量，作为树模型的基线输入。"""
    return pd.DataFrame({
        "mean": X.mean(axis=1).mean(axis=1),
        "std": X.std(axis=1).mean(axis=1),
        "slope": X[:, -1, :].mean(axis=1) - X[:, 0, :].mean(axis=1),
        "last": X[:, -1, :].mean(axis=1),
    })

baseline = lgb.LGBMRegressor(n_estimators=200, num_leaves=15, min_child_samples=100,
                             subsample=0.8, colsample_bytree=0.8, random_state=0)
baseline.fit(window_stats(trX), trY)
pred_base = baseline.predict(window_stats(vaX))
print("基线验证 MSE", round(float(np.mean((pred_base - vaY) ** 2)), 5))

# ---- 代码块 7：代码实现 ----

train_end = np.datetime64("2024-08-01")
valid_start = train_end + np.timedelta64(T + 20, "D")   # 缓冲期不小于窗口长度
tr_mask = dates <= train_end
va_mask = dates > valid_start
va_dates, va_codes = dates[va_mask], gcodes[va_mask]

model.load_state_dict(torch.load("lstm_best.pt"))
model.eval()
with torch.no_grad():
    pred = model(vaX_t).numpy()

score = pd.DataFrame({"date": va_dates, "code": va_codes,
                      "score": pred, "forward_5": vaY})

def daily_ic(g):
    if len(g) < 5:
        return np.nan
    return g["score"].corr(g["forward_5"], method="spearman")

ic = score.groupby("date").apply(daily_ic).dropna()
print("IC 均值", round(ic.mean(), 4),
      "ICIR", round(ic.mean() / ic.std(), 3),
      "期数", len(ic))
