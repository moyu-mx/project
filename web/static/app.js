const log = document.getElementById("chat-log");

const form = document.getElementById("chat-form");

const diagnose = document.getElementById("diagnose");

const mainEl = document.querySelector("main");

const layoutEl = document.querySelector(".layout");

const modeSelect = document.getElementById("chat-mode-select");



const TOOL_LABELS = {

  list_tables: "列出数据表",

  get_database_schema: "获取数据库结构",

  get_field_glossary: "获取字段对照",

  preview_table: "预览表数据",

  validate_sql_query: "校验 SQL",

};



const ECHARTS_URL = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js";

let echartsLoadPromise = null;



function loadEcharts() {

  if (typeof window.echarts !== "undefined") return Promise.resolve(window.echarts);

  if (echartsLoadPromise) return echartsLoadPromise;

  echartsLoadPromise = new Promise((resolve, reject) => {

    const script = document.createElement("script");

    script.src = ECHARTS_URL;

    script.async = true;

    script.onload = () => resolve(window.echarts);

    script.onerror = () => reject(new Error("ECharts 加载失败，将使用表格展示"));

    document.head.appendChild(script);

  });

  return echartsLoadPromise;

}



// ---------- 图表解读数据 ----------

let chartInsights = {};

try {

  const el = document.getElementById("chart-insights-data");

  if (el && el.textContent) chartInsights = JSON.parse(el.textContent);

} catch (e) {

  console.error("解析图表解读数据失败", e);

}



// ---------- 灯箱 ----------

const lightbox = document.getElementById("lightbox");

const lbTitle = document.getElementById("lb-title");

const lbChart = document.getElementById("lb-chart");

const lbText = document.getElementById("lb-text");

const dashboardChartStore = new Map();

const dashboardChartInstances = new Map();

let lightboxChartInstance = null;



function applyLegendLabelWhite(option) {

  const opt = JSON.parse(JSON.stringify(option));

  const white = "#ffffff";

  const legends = opt.legend ? (Array.isArray(opt.legend) ? opt.legend : [opt.legend]) : [];

  legends.forEach((l) => {

    l.textStyle = { ...(l.textStyle || {}), color: white };

  });

  (opt.series || []).forEach((s) => {

    if (s.label === false) return;

    s.label = { ...(s.label || {}), color: white };

    if (s.type === "pie" && Array.isArray(s.data)) {

      s.data.forEach((d) => {

        if (typeof d !== "object" || d === null || d.label === false) return;

        d.label = { ...(d.label || {}), color: white };

      });

    }

  });

  const graphics = opt.graphic ? (Array.isArray(opt.graphic) ? opt.graphic : [opt.graphic]) : [];

  graphics.forEach((g) => {

    if (g?.style?.text) g.style.fill = white;

  });

  return opt;

}



function toThumbnailOption(option) {

  const thumb = JSON.parse(JSON.stringify(option));

  const hideTitle = (title) => {

    if (!title) return;

    if (Array.isArray(title)) title.forEach((t) => { t.show = false; });

    else title.show = false;

  };

  hideTitle(thumb.title);

  if (thumb.legend) {

    if (Array.isArray(thumb.legend)) thumb.legend.forEach((l) => { l.show = false; });

    else thumb.legend.show = false;

  }

  delete thumb.graphic;

  thumb.tooltip = { show: false };

  thumb.animation = false;

  const normalizeAxis = (axis) => {

    if (!axis) return;

    const axes = Array.isArray(axis) ? axis : [axis];

    axes.forEach((a) => {

      if (!a) return;

      a.axisLabel = { ...(a.axisLabel || {}), show: false };

      a.name = "";

      a.axisTick = { show: false };

    });

  };

  normalizeAxis(thumb.xAxis);

  normalizeAxis(thumb.yAxis);

  thumb.grid = {

    ...(thumb.grid || {}),

    left: 6,

    right: 6,

    top: 6,

    bottom: 6,

    containLabel: false,

  };

  if (Array.isArray(thumb.series)) {

    thumb.series.forEach((s) => {

      s.label = { show: false };

      if (s.labelLine) s.labelLine = { show: false };

      if (s.type === "pie") {

        s.center = ["50%", "50%"];

        s.radius = "72%";

        if (Array.isArray(s.data)) {

          s.data = s.data.map((d) =>

            typeof d === "object" && d !== null

              ? { ...d, label: { show: false }, labelLine: { show: false } }

              : d

          );

        }

      }

    });

  }

  return thumb;

}



async function mountEchart(container, option, storeKey) {

  if (!container || !option) return null;

  try {

    const ec = await loadEcharts();

    if (storeKey && dashboardChartInstances.has(storeKey)) {

      dashboardChartInstances.get(storeKey).dispose();

    }

    const chart = ec.init(container);

    chart.setOption(option);

    if (storeKey) dashboardChartInstances.set(storeKey, chart);

    const resize = () => chart.resize();

    window.addEventListener("resize", resize);

    return chart;

  } catch (err) {

    console.error("图表渲染失败", err);

    container.textContent = "图表加载失败";

    return null;

  }

}



function openLightbox(chartKey) {

  if (!lightbox) return;

  const info = chartInsights[chartKey] || {};

  const payload = dashboardChartStore.get(chartKey);

  lbTitle.textContent = info.title || payload?.title || chartKey.replace(".png", "");

  lbText.textContent = payload?.analysis || info.analysis || "暂无分析说明，请先完成数据入库。";

  lightbox.classList.add("is-open");

  lightbox.setAttribute("aria-hidden", "false");

  document.body.classList.add("lightbox-open");

  if (lightboxChartInstance) {

    lightboxChartInstance.dispose();

    lightboxChartInstance = null;

  }

  if (lbChart) lbChart.innerHTML = "";

  if (payload?.echarts_option && lbChart) {

    setTimeout(async () => {

      lightboxChartInstance = await mountEchart(lbChart, applyLegendLabelWhite(payload.echarts_option));

    }, 30);

  }

}



function closeLightbox() {

  if (!lightbox) return;

  lightbox.classList.remove("is-open");

  lightbox.setAttribute("aria-hidden", "true");

  if (lightboxChartInstance) {

    lightboxChartInstance.dispose();

    lightboxChartInstance = null;

  }

  if (lbChart) lbChart.innerHTML = "";

  document.body.classList.remove("lightbox-open");

}



function bindDashboardChartInteractions() {

  document.querySelectorAll(".dashboard-chart").forEach((el) => {

    const open = () => openLightbox(el.dataset.chart);

    el.addEventListener("click", open);

    el.addEventListener("keydown", (e) => {

      if (e.key === "Enter" || e.key === " ") {

        e.preventDefault();

        open();

      }

    });

  });

}



async function reloadSectionCharts(section, options = {}) {

  const { yearFrom = null, yearTo = null, rfmYear = null, forecastParams = null } = options;

  const params = new URLSearchParams();

  if (section === "rfm" && rfmYear) {

    params.set("rfm_year", rfmYear);

  } else if (section === "forecast" && forecastParams) {

    Object.entries(forecastParams).forEach(([key, value]) => {

      if (value !== null && value !== undefined && value !== "") {

        params.set(key, String(value));

      }

    });

  } else if (yearFrom && yearTo) {

    params.set("year_from", yearFrom);

    params.set("year_to", yearTo);

  }

  const qs = params.toString();

  const res = await fetch(`/api/dashboard/charts/section/${section}${qs ? `?${qs}` : ""}`);

  const data = await res.json();

  if (!res.ok) throw new Error(data.detail || "图表加载失败");

  const nodes = document.querySelectorAll(`.dashboard-chart[data-section="${section}"]`);

  for (const el of nodes) {

    const chartId = el.dataset.chart;

    const payload = data.charts?.[chartId];

    if (payload) dashboardChartStore.set(chartId, payload);

    if (dashboardChartInstances.has(chartId)) {

      dashboardChartInstances.get(chartId).dispose();

      dashboardChartInstances.delete(chartId);

    }

    el.classList.remove("is-loading");

    el.innerHTML = "";

    if (!payload?.echarts_option) {

      el.textContent = payload?.error || "暂无图表数据";

      continue;

    }

    await mountEchart(el, toThumbnailOption(payload.echarts_option), chartId);

    const cap = el.closest("figure")?.querySelector("figcaption");

    if (cap && payload.title) cap.textContent = payload.title;

  }

  const salesNote = document.getElementById("sales-range-note");

  if (salesNote && section === "sales") {

    salesNote.textContent = data.year_from

      ? `已按 ${data.year_from}—${data.year_to} 年订单数据展示`

      : "默认展示全部年份；随上方数据概况年份范围联动更新";

  }

  const regionNote = document.getElementById("region-range-note");

  if (regionNote && section === "region") {

    regionNote.textContent = data.year_from

      ? `已按 ${data.year_from}—${data.year_to} 年订单数据展示`

      : "默认展示全部年份；随上方数据概况年份范围联动更新";

  }

  const rfmHint = document.getElementById("rfm-range-hint");

  if (rfmHint && section === "rfm") {

    rfmHint.textContent = data.rfm_year

      ? `当前展示 ${data.rfm_year} 年 RFM 客户价值分布`

      : "选择要查看的 RFM 快照年份";

  }

  const forecastHint = document.getElementById("forecast-hint");

  if (forecastHint && section === "forecast") {

    const fp = data.forecast_params || {};

    const salesModel = fp.sales_model === "polynomial" ? `多项式(${fp.sales_poly_degree}阶)` : "线性回归";

    const seasonModel = fp.seasonality_model === "linear_trend" ? "纯线性趋势" : "线性+季节指数";

    forecastHint.textContent = `已应用：销售额 ${salesModel} · 淡旺季 ${seasonModel} · Top${fp.region_top_n || 6} 区域 · 客单价 ML 融合权重 ${fp.aov_fusion_ml_weight ?? 0.55}`;

  }

  return data;

}



async function initDashboardCharts() {

  const nodes = document.querySelectorAll(".dashboard-chart");

  if (!nodes.length) return;

  nodes.forEach((el) => el.classList.add("is-loading"));

  try {

    const res = await fetch("/api/dashboard/charts");

    const data = await res.json();

    if (!res.ok) throw new Error("加载仪表盘图表失败");

    Object.entries(data.charts || {}).forEach(([chartId, payload]) => {

      dashboardChartStore.set(chartId, payload);

    });

    for (const el of nodes) {

      const chartId = el.dataset.chart;

      const payload = dashboardChartStore.get(chartId);

      el.classList.remove("is-loading");

      if (!payload?.echarts_option) {

        el.textContent = payload?.error || "暂无图表数据";

        continue;

      }

      await mountEchart(el, toThumbnailOption(payload.echarts_option), chartId);

    }

    bindDashboardChartInteractions();

  } catch (err) {

    console.error(err);

    nodes.forEach((el) => {

      el.classList.remove("is-loading");

      el.textContent = "图表加载失败";

    });

  }

}



initDashboardCharts();



// ---------- 数据概况年份筛选 ----------

function fillYearSelect(select, minYear, maxYear) {

  if (!select) return;

  const current = select.value;

  select.innerHTML = '<option value="">全部</option>';

  for (let y = minYear; y <= maxYear; y += 1) {

    const opt = document.createElement("option");

    opt.value = String(y);

    opt.textContent = String(y);

    select.appendChild(opt);

  }

  if (current && select.querySelector(`option[value="${current}"]`)) {

    select.value = current;

  }

}



function updateOverviewStatsDisplay(stats) {

  const map = {

    orders: document.getElementById("stat-orders"),

    customers: document.getElementById("stat-customers"),

    products: document.getElementById("stat-products"),

    markets: document.getElementById("stat-markets"),

  };

  Object.entries(map).forEach(([key, el]) => {

    if (el && stats[key] !== undefined) el.textContent = stats[key];

  });

  const hint = document.getElementById("overview-range-hint");

  if (!hint) return;

  if (stats.filtered) {

    hint.textContent = `已筛选 ${stats.year_from}—${stats.year_to} 年订单相关统计`;

  } else {

    hint.textContent = "默认展示全部数据";

  }

}



async function fetchOverviewStats(yearFrom, yearTo) {

  const params = new URLSearchParams();

  if (yearFrom && yearTo) {

    params.set("year_from", yearFrom);

    params.set("year_to", yearTo);

  }

  const qs = params.toString();

  const res = await fetch(`/api/overview/stats${qs ? `?${qs}` : ""}`);

  const data = await res.json();

  if (!res.ok) throw new Error(data.detail || "统计数据加载失败");

  return data;

}



async function initOverviewYearFilter() {

  const fromSelect = document.getElementById("overview-year-from");

  const toSelect = document.getElementById("overview-year-to");

  const resetBtn = document.getElementById("overview-year-reset");

  if (!fromSelect || !toSelect) return;

  try {

    const res = await fetch("/api/overview/years");

    const bounds = await res.json();

    if (!res.ok) throw new Error("年份范围加载失败");

    fillYearSelect(fromSelect, bounds.min_year, bounds.max_year);

    fillYearSelect(toSelect, bounds.min_year, bounds.max_year);

  } catch (err) {

    console.error(err);

    return;

  }

  const applyFilter = async () => {

    const fromVal = fromSelect.value;

    const toVal = toSelect.value;

    if ((fromVal && !toVal) || (!fromVal && toVal)) {

      const hint = document.getElementById("overview-range-hint");

      if (hint) hint.textContent = "请同时选择起止年份";

      return;

    }

    try {

      const stats = await fetchOverviewStats(fromVal || null, toVal || null);

      updateOverviewStatsDisplay(stats);

      await reloadSectionCharts("sales", { yearFrom: fromVal || null, yearTo: toVal || null });

      await reloadSectionCharts("region", { yearFrom: fromVal || null, yearTo: toVal || null });

    } catch (err) {

      console.error(err);

    }

  };

  fromSelect.addEventListener("change", () => {

    if (fromSelect.value && toSelect.value && Number(fromSelect.value) > Number(toSelect.value)) {

      toSelect.value = fromSelect.value;

    }

    applyFilter();

  });

  toSelect.addEventListener("change", () => {

    if (fromSelect.value && toSelect.value && Number(fromSelect.value) > Number(toSelect.value)) {

      fromSelect.value = toSelect.value;

    }

    applyFilter();

  });

  if (resetBtn) {

    resetBtn.addEventListener("click", () => {

      fromSelect.value = "";

      toSelect.value = "";

      applyFilter();

    });

  }

}



initOverviewYearFilter();



async function initRfmYearFilter() {

  const select = document.getElementById("rfm-year-select");

  if (!select) return;

  try {

    const res = await fetch("/api/dashboard/rfm/years");

    const data = await res.json();

    if (!res.ok) throw new Error("RFM 年份加载失败");

    select.innerHTML = "";

    (data.years || []).forEach((y) => {

      const opt = document.createElement("option");

      opt.value = String(y);

      opt.textContent = String(y);

      select.appendChild(opt);

    });

    select.value = String(data.default_year || data.years?.[0] || "");

    await reloadSectionCharts("rfm", { rfmYear: select.value });

    select.addEventListener("change", async () => {

      try {

        await reloadSectionCharts("rfm", { rfmYear: select.value });

      } catch (err) {

        console.error(err);

      }

    });

  } catch (err) {

    console.error(err);

  }

}



initRfmYearFilter();



let forecastOptionsMeta = null;

let forecastDefaults = {};



function collectForecastParams() {

  const fields = document.querySelectorAll("#forecast-fields [data-forecast-field]");

  const params = {};

  fields.forEach((el) => {

    const name = el.dataset.forecastField;

    if (!name || el.closest(".forecast-field.is-hidden")) return;

    params[name] = el.type === "number" ? el.value : el.value;

  });

  return params;

}



function updateForecastFieldVisibility() {

  const fields = document.querySelectorAll("#forecast-fields .forecast-field[data-visible-when]");

  fields.forEach((wrap) => {

    let visible = true;

    try {

      const rule = JSON.parse(wrap.dataset.visibleWhen || "{}");

      visible = Object.entries(rule).every(([key, expected]) => {

        const control = document.querySelector(`#forecast-fields [data-forecast-field="${key}"]`);

        return control && control.value === String(expected);

      });

    } catch (e) {

      visible = true;

    }

    wrap.classList.toggle("is-hidden", !visible);

  });

}



function renderForecastControls(meta) {

  const container = document.getElementById("forecast-fields");

  if (!container || !meta?.groups) return;

  container.innerHTML = "";

  meta.groups.forEach((group) => {

    const groupEl = document.createElement("div");

    groupEl.className = "forecast-group";

    if (group.collapsible) groupEl.classList.add("is-collapsed");

    const titleBtn = document.createElement("button");

    titleBtn.type = "button";

    titleBtn.className = "forecast-group-toggle";

    titleBtn.textContent = group.label;

    if (group.collapsible) {

      titleBtn.addEventListener("click", () => {

        groupEl.classList.toggle("is-collapsed");

      });

    }

    const body = document.createElement("div");

    body.className = "forecast-group-body";

    (group.fields || []).forEach((field) => {

      const fieldWrap = document.createElement("div");

      fieldWrap.className = "forecast-field";

      if (field.visible_when) {

        fieldWrap.dataset.visibleWhen = JSON.stringify(field.visible_when);

      }

      const label = document.createElement("label");

      label.textContent = field.label;

      label.setAttribute("for", `forecast-${field.name}`);

      let input;

      if (field.type === "select") {

        input = document.createElement("select");

        (field.options || []).forEach((opt) => {

          const option = document.createElement("option");

          option.value = opt.value;

          option.textContent = opt.label;

          input.appendChild(option);

        });

      } else {

        input = document.createElement("input");

        input.type = "number";

        if (field.min != null) input.min = String(field.min);

        if (field.max != null) input.max = String(field.max);

        if (field.step != null) input.step = String(field.step);

      }

      input.id = `forecast-${field.name}`;

      input.dataset.forecastField = field.name;

      const defaultVal = meta.defaults?.[field.name] ?? field.default ?? field.recommended;

      input.value = String(defaultVal);

      input.addEventListener("change", updateForecastFieldVisibility);

      fieldWrap.appendChild(label);

      fieldWrap.appendChild(input);

      body.appendChild(fieldWrap);

    });

    groupEl.appendChild(titleBtn);

    groupEl.appendChild(body);

    container.appendChild(groupEl);

  });

  updateForecastFieldVisibility();

}



function applyForecastDefaults(meta) {

  if (!meta?.defaults) return;

  Object.entries(meta.defaults).forEach(([name, value]) => {

    const el = document.querySelector(`#forecast-fields [data-forecast-field="${name}"]`);

    if (el) el.value = String(value);

  });

  updateForecastFieldVisibility();

}



async function initForecastControls() {

  const applyBtn = document.getElementById("forecast-apply-btn");

  const resetBtn = document.getElementById("forecast-reset-btn");

  if (!document.getElementById("forecast-fields")) return;

  try {

    const res = await fetch("/api/dashboard/forecast/options");

    const meta = await res.json();

    if (!res.ok) throw new Error("预测参数配置加载失败");

    forecastOptionsMeta = meta;

    forecastDefaults = meta.defaults || {};

    renderForecastControls(meta);

    await reloadSectionCharts("forecast", { forecastParams: forecastDefaults });

    const runApply = async () => {

      try {

        applyBtn.disabled = true;

        await reloadSectionCharts("forecast", { forecastParams: collectForecastParams() });

      } catch (err) {

        console.error(err);

        const hint = document.getElementById("forecast-hint");

        if (hint) hint.textContent = err.message || "预测刷新失败";

      } finally {

        applyBtn.disabled = false;

      }

    };

    applyBtn?.addEventListener("click", runApply);

    resetBtn?.addEventListener("click", async () => {

      applyForecastDefaults(forecastOptionsMeta);

      await runApply();

    });

  } catch (err) {

    console.error(err);

    const hint = document.getElementById("forecast-hint");

    if (hint) hint.textContent = "预测参数面板加载失败";

  }

}



initForecastControls();



if (lightbox) {

  lightbox.querySelector(".lightbox-mask")?.addEventListener("click", closeLightbox);

  lightbox.querySelector(".lightbox-close")?.addEventListener("click", closeLightbox);

}

document.addEventListener("keydown", (e) => {

  if (e.key === "Escape" && lightbox?.classList.contains("is-open")) closeLightbox();

});



// ---------- 导航 ----------

function scrollToSection(id) {

  const target = document.getElementById(id);

  if (!target || !mainEl) return;

  const mainRect = mainEl.getBoundingClientRect();

  const targetRect = target.getBoundingClientRect();

  mainEl.scrollTo({

    top: mainEl.scrollTop + targetRect.top - mainRect.top - 16,

    behavior: "smooth",

  });

}



document.querySelectorAll("nav a[href^='#']").forEach((link) => {

  link.addEventListener("click", (e) => {

    e.preventDefault();

    const id = link.getAttribute("href").slice(1);

    scrollToSection(id);

    document.querySelectorAll("nav a").forEach((a) => a.classList.remove("active"));

    link.classList.add("active");

    history.replaceState(null, "", `#${id}`);

  });

});



if (location.hash) {

  const init = document.querySelector(`nav a[href="${location.hash}"]`);

  if (init) {

    init.classList.add("active");

    requestAnimationFrame(() => scrollToSection(location.hash.slice(1)));

  }

}



// 鼠标滚轮：在 layout 区域滚动时同步滚动 main

if (layoutEl && mainEl) {

  layoutEl.addEventListener(

    "wheel",

    (e) => {

      if (e.target.closest("nav") || e.target.closest("#chat-log")) return;

      if (mainEl.scrollHeight <= mainEl.clientHeight) return;

      mainEl.scrollTop += e.deltaY;

      e.preventDefault();

    },

    { passive: false }

  );

}



// ---------- 调用方式选择 ----------

async function initModeSelect() {

  if (!modeSelect) return;

  try {

    const res = await fetch("/api/chat/config");

    const cfg = await res.json();

    const apiOption = modeSelect.querySelector('option[value="api"]');

    if (apiOption) {

      if (cfg.api_enabled) {

        apiOption.disabled = false;

        apiOption.textContent = "API 模式";

      } else {

        apiOption.disabled = true;

        apiOption.textContent = "API 模式（即将开放）";

      }

    }

    modeSelect.value = cfg.default_mode || "local";

  } catch {

    modeSelect.value = "local";

  }

}

initModeSelect();



function getSelectedMode() {

  return modeSelect ? modeSelect.value : "local";

}



function formatTools(tools) {

  if (!tools || !tools.length) return "—";

  return tools.map((t) => TOOL_LABELS[t] || t).join("、");

}



function modeLabel(mode) {

  return mode === "api" ? "API 模式" : "本地模式";

}



// ---------- 聊天 ----------

function addMsg(text, cls, extra) {

  const div = document.createElement("div");

  div.className = `msg ${cls}`;

  div.innerHTML = text + (extra || "");

  log.appendChild(div);

  log.scrollTop = log.scrollHeight;

}



function renderTable(columns, rows) {

  if (!rows.length) return "<p>无符合条件的数据（数值需 &gt; 0.1）</p>";

  let html = "<table><tr>" + columns.map((c) => `<th>${c}</th>`).join("") + "</tr>";

  for (const row of rows) {

    html += "<tr>" + row.map((v) => `<td>${v ?? ""}</td>`).join("") + "</tr>";

  }

  return html + "</table>";

}



let chatChartCounter = 0;



async function renderQueryResult(data) {

  const d = data.display || {};

  const filterNote = data.filtered_out

    ? `<p class="filter-note">已过滤 ${data.filtered_out} 条数值 ≤ ${d.value_min ?? 0.1} 的记录</p>`

    : "";

  const meta = `<div class="result-meta">

    <span class="result-tag">${d.template_label || "表格"}</span>

    <strong>${d.chart_title || "查询结果"}</strong>

    <p class="result-summary">${d.summary || ""}</p>

    ${filterNote}

  </div>`;



  if (d.template !== "table" && data.echarts_option) {

    const chartId = `chat-chart-${++chatChartCounter}`;

    const body = `<div id="${chartId}" class="chat-chart-box"></div>`;

    setTimeout(async () => {

      const el = document.getElementById(chartId);

      if (!el) return;

      try {

        const chart = await mountEchart(el, applyLegendLabelWhite(data.echarts_option));

      } catch {

        el.outerHTML = renderTable(data.columns, data.rows);

      }

    }, 50);

    return meta + body;

  }

  return meta + renderTable(data.columns, data.rows);

}



if (form) {

  form.addEventListener("submit", async (e) => {

    e.preventDefault();

    const q = document.getElementById("question").value.trim();

    if (!q) return;

    addMsg(q, "user");

    document.getElementById("question").value = "";

    try {

      const res = await fetch("/api/chat", {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({ question: q, mode: getSelectedMode() }),

      });

      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "查询失败");

      const label = modeLabel(data.mode);

      const disp = data.display || {};

      const resultHtml = await renderQueryResult(data);

      addMsg(

        `查询结果（${label} · ${disp.template_label || "表格"}）`,

        "bot",

        `<pre class="sql-block">${data.sql}</pre>${resultHtml}`

      );

      diagnose.classList.remove("hidden");

      diagnose.innerHTML = `调用方式：${label} | 模板：${disp.template_label || "—"} | 工具：${formatTools(data.tools_used)} | 展示 ${data.row_count} 条

        <details><summary>推理过程</summary><pre class="reasoning">${data.reasoning || ""}</pre></details>

        <button type="button" data-query-id="${data.query_id}" data-correct="true">正确</button>

        <button type="button" data-query-id="${data.query_id}" data-correct="false">错误</button>`;

      diagnose.querySelectorAll("button[data-query-id]").forEach((btn) => {

        btn.addEventListener("click", () => {

          feedback(btn.dataset.queryId, btn.dataset.correct === "true");

        });

      });

    } catch (err) {

      addMsg(`错误：${err.message}`, "bot");

    }

  });

}



async function feedback(queryId, correct) {

  await fetch("/api/chat/feedback", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: JSON.stringify({ query_id: queryId, correct }),

  });

  diagnose.innerHTML += ` | 已记录反馈：${correct ? "正确" : "错误"}`;

}



window.feedback = feedback;


