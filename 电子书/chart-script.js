/* ============================================================
   交互图：TradingView Lightweight Charts
   每个指标章一张，三窗格：K 线（可叠加均线）/ 成交量 / 指标。
   静态图保留在同一容器里，打印或初始化失败时登场。
   ============================================================ */
(function () {
  var payload = null;
  try {
    var raw = document.getElementById('chart-data');
    if (raw) payload = JSON.parse(raw.textContent);
  } catch (e) { payload = null; }
  if (!payload || typeof document === 'undefined') return;

  var MOUNTED = [];

  // A 股习惯：涨红跌绿
  function palette() {
    var night = document.documentElement.getAttribute('data-theme') === 'night';
    return night
      ? { bg: '#15181d', text: '#b8c2cc', grid: '#232820', line: '#4fa3f7',
          up: '#ef5350', down: '#26a69a', border: '#2a2f36' }
      : { bg: '#ffffff', text: '#37474f', grid: '#eef1f4', line: '#1e6fd9',
          up: '#e53935', down: '#26a69a', border: '#dfe3e8' };
  }

  function toBars(o) {
    var out = [];
    for (var i = 0; i < o.t.length; i++) {
      out.push({ time: o.t[i], open: o.o[i], high: o.h[i], low: o.l[i], close: o.c[i] });
    }
    return out;
  }

  function toLine(t, vals) {
    var out = [];
    for (var i = 0; i < t.length; i++) {
      if (vals[i] === null || vals[i] === undefined) continue;
      out.push({ time: t[i], value: vals[i] });
    }
    return out;
  }

  function build(el, ch) {
    var spec = payload.chapters[ch];
    if (!spec) throw new Error('第 ' + ch + ' 章没有图表数据');
    var box = el.querySelector('.chart-live');
    if (!box) return;

    var p = palette();
    var o = payload.ohlc;

    // 清掉“图表加载中”
    var ld = box.querySelector('.ch-loading');
    if (ld) ld.parentNode.removeChild(ld);

    var chart = LightweightCharts.createChart(box, {
      width: box.clientWidth || 720,
      height: box.clientHeight || 440,
      layout: {
        background: { color: p.bg },
        textColor: p.text,
        fontFamily: '-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
        fontSize: 11,
        panes: { separatorColor: p.border, separatorHoverColor: p.line }
      },
      grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
      rightPriceScale: { borderColor: p.border },
      timeScale: { borderColor: p.border, rightOffset: 3, barSpacing: 4 },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      localization: {
        locale: 'zh-CN',
        priceFormatter: function (v) {
          return Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(3);
        }
      }
    });

    /* ---- 窗格 0：K 线 ---- */
    var candle = chart.addSeries(LightweightCharts.CandlestickSeries, {
      upColor: p.up, downColor: p.down,
      borderUpColor: p.up, borderDownColor: p.down,
      wickUpColor: p.up, wickDownColor: p.down
    }, 0);
    candle.setData(toBars(o));

    /* 与价格同量纲的指标直接叠在 K 线窗格里 */
    if (spec.pane === 'price') {
      var line = chart.addSeries(LightweightCharts.LineSeries, {
        color: p.line, lineWidth: 2,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false
      }, 0);
      line.setData(toLine(o.t, spec.vals));
    }

    /* ---- 窗格 1：成交量 ---- */
    var volPane = chart.addPane();
    volPane.setStretchFactor(0.24);
    var vol = chart.addSeries(LightweightCharts.HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceLineVisible: false, lastValueVisible: false
    }, 1);
    var vd = [];
    for (var j = 0; j < o.t.length; j++) {
      vd.push({
        time: o.t[j],
        value: o.v[j],
        color: (o.c[j] >= o.o[j] ? p.up : p.down) + '59'
      });
    }
    vol.setData(vd);

    /* ---- 窗格 2：指标（与价格不同量纲时才开） ---- */
    if (spec.pane !== 'price') {
      var indPane = chart.addPane();
      indPane.setStretchFactor(0.32);

      if (spec.pane === 'hist') {
        var hist = chart.addSeries(LightweightCharts.HistogramSeries, {
          priceLineVisible: false, lastValueVisible: false, base: 0
        }, 2);
        var hd = [];
        for (var k = 0; k < o.t.length; k++) {
          var v2 = spec.vals[k];
          if (v2 === null || v2 === undefined) continue;
          hd.push({ time: o.t[k], value: v2, color: v2 >= 0 ? p.up : p.down });
        }
        hist.setData(hd);
      } else {
        var sub = chart.addSeries(LightweightCharts.LineSeries, {
          color: p.line, lineWidth: 2,
          priceLineVisible: false, lastValueVisible: true
        }, 2);
        sub.setData(toLine(o.t, spec.vals));
      }
    }

    /* 先看最近一年，读者可以拖回去看更早 */
    var n = o.t.length;
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 240), to: n + 2 });

    var ro = null;
    if (window.ResizeObserver) {
      ro = new ResizeObserver(function () {
        try { chart.applyOptions({ width: box.clientWidth }); } catch (err) {}
      });
      ro.observe(box);
    }

    MOUNTED.push({ chart: chart, ro: ro });
  }

  function destroyAll() {
    for (var i = 0; i < MOUNTED.length; i++) {
      if (MOUNTED[i].ro) MOUNTED[i].ro.disconnect();
      try { MOUNTED[i].chart.remove(); } catch (e) {}
    }
    MOUNTED = [];
  }

  function initCharts(root) {
    root = root || document.getElementById('page') || document;
    var shells = root.querySelectorAll ? root.querySelectorAll('.chart-shell[data-ch]') : [];
    if (!shells.length) return;

    destroyAll();

    if (typeof LightweightCharts === 'undefined') {
      // 库没加载成功：全部退回静态图，不留白
      for (var i = 0; i < shells.length; i++) shells[i].classList.add('chart-failed');
      return;
    }

    for (var j = 0; j < shells.length; j++) {
      try {
        build(shells[j], shells[j].getAttribute('data-ch'));
      } catch (err) {
        if (window.console) console.warn('图表初始化失败：', err);
        shells[j].classList.add('chart-failed');
      }
    }
  }

  /* #page 换章时重新挂载。只看直接子节点，避免图表内部 canvas
     的变化触发递归。 */
  var page = document.getElementById('page');
  if (page && window.MutationObserver) {
    new MutationObserver(function () { initCharts(page); })
      .observe(page, { childList: true });
  }

  /* 主题切换后按新配色重绘 */
  if (window.MutationObserver) {
    new MutationObserver(function () {
      if (MOUNTED.length) initCharts(page);
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  }

  /* ---- 打印：把全部章节铺开，静态图随之出场 ----
     不这么做，Cmd+P 只会打出当前一屏。 */
  function buildPrintAll() {
    var host = document.getElementById('print-all');
    if (!host) return;
    if (host.dataset.built === '1') return;
    // 主脚本用 const BOOK 声明，不挂在 window 上，
    // 只能在作用域链里按名字取，取不到才算没准备好。
    var data = null;
    try { data = (typeof BOOK !== 'undefined') ? BOOK : null; } catch (e) { data = null; }
    if (!data) return;
    var h = '';
    for (var i = 0; i < data.length; i++) {
      var mod = data[i];
      for (var j = 0; j < mod.chapters.length; j++) {
        var c = mod.chapters[j];
        h += '<section class="print-ch chapter-body" data-ch="' + c.n + '">'
          + '<div class="print-mod">模块 ' + String(mod.no).padStart(2, '0')
          + ' · ' + mod.name + '</div>'
          + c.html + '</section>';
      }
    }
    host.innerHTML = h;
    host.dataset.built = '1';
  }

  window.addEventListener('beforeprint', function () {
    buildPrintAll();
    // 打印时用不到交互图，直接标成失败态让静态图接手，
    // 免得 Canvas 在纸上留空白。
    var shells = document.querySelectorAll('.chart-shell[data-ch]');
    for (var i = 0; i < shells.length; i++) shells[i].classList.add('chart-failed');
  });

  /* 首屏：主脚本可能已经渲染完章节，这里补一次 */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initCharts(page); });
  } else {
    initCharts(page);
  }
})();
