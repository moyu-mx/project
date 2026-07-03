const log = document.getElementById("chat-log");
const form = document.getElementById("chat-form");
const diagnose = document.getElementById("diagnose");
const mainEl = document.querySelector("main");
const modeSelect = document.getElementById("chat-mode-select");

const TOOL_LABELS = {
  list_tables: "列出数据表",
  get_database_schema: "获取数据库结构",
  get_field_glossary: "获取字段对照",
  preview_table: "预览表数据",
};

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
const lbImage = document.getElementById("lb-image");
const lbText = document.getElementById("lb-text");

function openLightbox(chartKey, imgSrc) {
  if (!lightbox) return;
  const info = chartInsights[chartKey] || {};
  lbTitle.textContent = info.title || chartKey.replace(".png", "");
  lbImage.src = imgSrc;
  lbImage.alt = lbTitle.textContent;
  lbText.textContent = info.analysis || "暂无分析说明，请先完成数据入库。";
  lightbox.hidden = false;
  document.body.classList.add("lightbox-open");
}

function closeLightbox() {
  if (!lightbox) return;
  lightbox.hidden = true;
  lbImage.src = "";
  document.body.classList.remove("lightbox-open");
}

document.querySelectorAll(".chart-thumb").forEach((img) => {
  img.addEventListener("click", () => openLightbox(img.dataset.chart, img.src));
});

if (lightbox) {
  lightbox.querySelector(".lightbox-mask").addEventListener("click", closeLightbox);
  lightbox.querySelector(".lightbox-close").addEventListener("click", closeLightbox);
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && lightbox && !lightbox.hidden) closeLightbox();
});

// ---------- 导航 ----------
document.querySelectorAll("nav a[href^='#']").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    const id = link.getAttribute("href").slice(1);
    const target = document.getElementById(id);
    if (!target || !mainEl) return;
    const mainRect = mainEl.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    mainEl.scrollTo({
      top: mainEl.scrollTop + targetRect.top - mainRect.top - 16,
      behavior: "smooth",
    });
    document.querySelectorAll("nav a").forEach((a) => a.classList.remove("active"));
    link.classList.add("active");
    history.replaceState(null, "", `#${id}`);
  });
});

if (location.hash) {
  const init = document.querySelector(`nav a[href="${location.hash}"]`);
  if (init) init.click();
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

function renderQueryResult(data) {
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

  let body = "";
  if (d.template !== "table" && data.echarts_option && typeof echarts !== "undefined") {
    const chartId = `chat-chart-${++chatChartCounter}`;
    body = `<div id="${chartId}" class="chat-chart-box"></div>`;
    setTimeout(() => {
      const el = document.getElementById(chartId);
      if (!el) return;
      const chart = echarts.init(el);
      chart.setOption(data.echarts_option);
      window.addEventListener("resize", () => chart.resize());
    }, 50);
  } else {
    body = renderTable(data.columns, data.rows);
  }
  return meta + body;
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
      addMsg(
        `查询结果（${label} · ${disp.template_label || "表格"}）`,
        "bot",
        `<pre class="sql-block">${data.sql}</pre>${renderQueryResult(data)}`
      );
      diagnose.classList.remove("hidden");
      diagnose.innerHTML = `调用方式：${label} | 模板：${disp.template_label || "—"} | 工具：${formatTools(data.tools_used)} | 耗时：${data.elapsed_ms} 毫秒 | 展示 ${data.row_count} 条
        <details><summary>推理过程</summary><pre class="reasoning">${data.reasoning || ""}</pre></details>
        <button onclick="feedback('${data.query_id}', true)">正确</button>
        <button onclick="feedback('${data.query_id}', false)">错误</button>`;
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
