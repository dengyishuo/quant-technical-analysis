# ============================================================
# R 示例数据准备（5 只 A 股蓝筹面板，含因子与未来收益列）
#
# 本文件由 scripts/extract_code.py 自动生成，请勿直接编辑。
# 修改代码请改 Markdown 源稿（模块02-因子检验方法/第007章），再重新运行提取脚本。
# ============================================================
library(quantmod)
library(dplyr)

codes <- c("600519.SS", "600036.SS", "601318.SS", "300750.SZ", "000858.SZ")

frames <- lapply(codes, function(cd) {
  x <- local({
    # 从本地 CSV 取该标的，转成 quantmod 可用的 xts
    .p <- read.csv("data/parquet/panel_blue_chip.csv", stringsAsFactors = FALSE)
    .p <- .p[.p$code == cd, ]
    .x <- xts::xts(.p[, c("open", "high", "low", "close", "volume", "adjusted")],
                       order.by = as.Date(.p$date))
    colnames(.x) <- c("Open", "High", "Low", "Close", "Volume", "Adjusted")
    .x
  })
  d <- data.frame(date = index(x), code = cd, close = as.numeric(Ad(x)))
  d$sma20 <- zoo::rollmean(d$close, 20, fill = NA, align = "right")
  d$sma_dev <- d$close / d$sma20 - 1
  # 未来一期收益：末行无未来值，记为 NA
  d$forward_1 <- c(diff(d$close) / d$close[-1], NA)
  d
})

panel <- bind_rows(frames)

ic <- cross_section_ic(panel, "sma_dev", "forward_1")
print(ic_summary(ic))
