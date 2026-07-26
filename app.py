# -*- coding: utf-8 -*-
"""
app.py — 图书馆 NL2SQL 原型系统（Streamlit 界面 · 双语精致版）
Library NL2SQL Prototype — bilingual, paper-archive aesthetic.
运行 / Run: streamlit run app.py
"""
import sqlite3

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

from src.glossary import match_glossary
from src.llm_client import LLMClient
from src.prompts import METHODS, METHOD_NAMES, build_prompt, parse_model_output
from src.safety import validate_sql

load_dotenv()
DB_PATH = "data/library.db"

st.set_page_config(page_title="Library NL2SQL", page_icon="📖", layout="wide",
                   initial_sidebar_state="expanded")

T = {
    "zh": {
        "title": "图书馆 NL2SQL 原型系统",
        "subtitle": "Design Science Research Artifact · 自然语言馆藏查询",
        "lang_label": "语言 / Language", "model": "大语言模型", "method": "提示工程方法",
        "params": "生成参数", "schema_title": "测试数据库 Schema", "rows": "行",
        "input_header": "自然语言查询",
        "input_ph": "用日常语言描述您想查询的内容，例如：查找2025年出版的所有计算机科学类图书",
        "pick_example": "（选择一个示例）", "run": "生 成 并 执 行", "empty_warn": "请输入查询内容",
        "s1": "① 术语标准化（预处理层）",
        "s1_none": "未命中术语词典条目，查询原文直接进入下一层",
        "s2": "② 构建的完整 Prompt", "s3": "③ LLM 推理",
        "sl_map": "Schema 链接映射", "reasoning": "推理过程（CoT）",
        "s4": "④ 安全校验（后处理层）",
        "safe_ok": "已校验 · 单条只读 SELECT 语句，放行执行", "safe_block": "已拦截 · 原因",
        "s5": "⑤ 执行结果", "result_rows": "行结果",
        "metric_lat": "推理延迟", "metric_in": "输入 Tokens", "metric_out": "输出 Tokens",
        "metric_method": "提示方法", "spinner": "模型生成中…", "api_fail": "API 调用失败",
        "init_fail": "模型初始化失败，请检查 .env 中的 API 密钥",
        "exec_fail": "执行层报错（可记录为错误案例）",
        "footer": "测试数据库为完全虚构的模拟数据，不含任何真实读者信息。系统仅允许只读 SELECT 查询。",
        "examples_list": [
            "查找2025年出版的所有计算机科学类图书",
            "统计2025年各学院读者的借阅总量，按借阅量从高到低排列",
            "哪些读者借过《数据库系统概念》？列出他们的姓名和学院",
            "找出借阅量超过其所在学院平均借阅量的读者",
            "馆藏地在三楼、目前在馆可借的图书有哪些",
        ],
    },
    "en": {
        "title": "Library NL2SQL Prototype",
        "subtitle": "Design Science Research Artifact · Natural-Language Catalog Query",
        "lang_label": "语言 / Language", "model": "Language Model", "method": "Prompt Method",
        "params": "Generation Params", "schema_title": "Test Database Schema", "rows": "rows",
        "input_header": "Natural-Language Query",
        "input_ph": "Describe what you want to find in plain language, e.g., Find all computer science books published in 2025",
        "pick_example": "(pick an example)", "run": "G E N E R A T E   &   R U N",
        "empty_warn": "Please enter a query",
        "s1": "① Term Normalization (Preprocessing Layer)",
        "s1_none": "No glossary term matched; the raw query proceeds to the next layer",
        "s2": "② Constructed Prompt", "s3": "③ LLM Inference",
        "sl_map": "Schema Linking Map", "reasoning": "Reasoning (CoT)",
        "s4": "④ Safety Validation (Post-processing Layer)",
        "safe_ok": "Validated · single read-only SELECT, cleared for execution",
        "safe_block": "Blocked · reason",
        "s5": "⑤ Execution Result", "result_rows": "rows returned",
        "metric_lat": "Latency", "metric_in": "Input Tokens", "metric_out": "Output Tokens",
        "metric_method": "Prompt Method", "spinner": "Generating…", "api_fail": "API call failed",
        "init_fail": "Model init failed; check API keys in .env",
        "exec_fail": "Execution error (can be logged as an error case)",
        "footer": "The test database is fully synthetic and contains no real reader information. Only read-only SELECT queries are permitted.",
        "examples_list": [
            "Find all computer science books published in 2025",
            "Total loans by each department in 2025, ordered from high to low",
            "Which readers borrowed 'Database System Concepts'? List their names and departments",
            "Find readers whose loan count exceeds their department average",
            "Books located on the 3rd floor that are currently available",
        ],
    },
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@600;700&family=Noto+Serif:wght@600;700&display=swap');
:root{
  --paper:#F4F6F3; --panel:#FFFFFF; --ink:#1C2B26; --ink-soft:#4A5A54;
  --line:#D9E0DA; --seal:#9E2B25; --seal-soft:#F6E9E8;
  --spruce:#23473C; --spruce-soft:#E7EEEA; --ok:#2E6B4F;
}
/* 强制整体浅色背景与深色文字，覆盖 Streamlit 深色主题 */
.stApp, .main, section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div{
  background:var(--paper) !important;
}
section[data-testid="stSidebar"]{ background:var(--panel) !important; border-right:1px solid var(--line); }
/* 所有文字默认深色（关键修复：防止深色主题下文字发白） */
.stApp, .stApp p, .stApp span, .stApp label, .stApp div,
.stMarkdown, .stRadio, .stSelectbox, .stCaption,
section[data-testid="stSidebar"] *{ color:var(--ink) !important; }
.main .block-container{ padding-top:2rem; max-width:1150px; }

.hdr{ border-bottom:2px solid var(--ink); padding-bottom:14px; margin-bottom:22px; }
.hdr-title{ font-family:'Noto Serif SC','Noto Serif',serif !important; font-size:28px; font-weight:700;
  color:var(--ink) !important; letter-spacing:.5px; margin:0; }
.hdr-title em{ font-style:normal; color:var(--seal) !important; }
.hdr-sub{ color:var(--ink-soft) !important; font-size:13px; margin-top:4px; }

section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] .stSelectbox label{ font-weight:600; color:var(--spruce) !important; }

.stage-label{ font-family:ui-monospace,monospace; font-size:11px; letter-spacing:1.5px;
  color:var(--ink-soft) !important; text-transform:uppercase; margin:16px 0 6px; }

/* 输入框：强制浅色底、深色字（修复深色输入框问题） */
.stTextArea textarea, textarea{
  background:#FCFDFC !important; color:var(--ink) !important;
  border:1.5px solid var(--line) !important; border-radius:8px !important; font-size:15px !important;
}
.stTextArea textarea::placeholder{ color:#9AA8A2 !important; }
/* 下拉框浅色 */
.stSelectbox div[data-baseweb="select"]>div{ background:#FCFDFC !important; color:var(--ink) !important; }

.stButton>button{ background:var(--ink) !important; color:#fff !important; border:none; border-radius:8px;
  font-weight:600; letter-spacing:2px; padding:12px 0; width:100%; transition:.15s; }
.stButton>button:hover{ background:var(--spruce) !important; color:#fff !important; }
.stButton>button *{ color:#fff !important; }

.chip{ display:inline-block; background:var(--paper); border:1px solid var(--line);
  border-radius:6px; padding:4px 10px; margin:3px 4px 3px 0; font-size:13px; color:var(--ink) !important; }
.chip b{ color:var(--seal) !important; } .chip code{ color:var(--spruce) !important; font-size:12px; }

.stamp{ display:inline-block; font-family:'Noto Serif',serif; font-weight:700; font-size:13px;
  letter-spacing:2px; color:var(--seal) !important; border:2.5px solid var(--seal); border-radius:6px;
  padding:5px 13px; transform:rotate(-3deg); background:transparent; }
.stamp.blk{ color:#fff !important; background:var(--seal); }

[data-testid="stDataFrame"]{ border:1.5px solid var(--ink); border-radius:4px; }
[data-testid="stMetric"]{ background:var(--paper) !important; border:1px solid var(--line);
  border-radius:8px; padding:10px 12px; }
[data-testid="stMetricValue"]{ color:var(--spruce) !important; font-family:ui-monospace,monospace; }
[data-testid="stMetricLabel"]{ color:var(--ink-soft) !important; }

footer, #MainMenu, header[data-testid="stHeader"]{ display:none !important; }
.foot{ margin-top:26px; padding-top:12px; border-top:1px solid var(--line);
  color:var(--ink-soft) !important; font-size:11.5px; line-height:1.7; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


cfg = load_config()

if "lang" not in st.session_state:
    st.session_state.lang = "zh"

with st.sidebar:
    st.markdown("### 📖 Library NL2SQL")
    lang = st.radio(T[st.session_state.lang]["lang_label"], ["中文", "English"],
                    index=0 if st.session_state.lang == "zh" else 1, horizontal=True)
    new_lang = "zh" if lang == "中文" else "en"
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()  # 语言变化立即整页重绘
    L = T[st.session_state.lang]
    st.divider()
    model_name = st.selectbox(L["model"], list(cfg["models"].keys()))
    method = st.radio(L["method"], METHODS, format_func=lambda m: METHOD_NAMES[m])
    st.divider()
    st.caption(f"{L['params']}: temperature={cfg['generation']['temperature']} · "
               f"max_tokens={cfg['generation']['max_tokens']} · SELECT-ONLY")
    with st.expander(L["schema_title"]):
        conn = sqlite3.connect(DB_PATH)
        for t in ["books", "readers", "borrow_records", "categories", "publishers", "locations"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
            st.markdown(f"**{t}** ({n} {L['rows']})  \n`{' · '.join(cols)}`")
        conn.close()

L = T[st.session_state.lang]

title_html = L["title"].replace("NL2SQL", "<em>NL2SQL</em>")
st.markdown(f'<div class="hdr"><p class="hdr-title">{title_html}</p>'
            f'<p class="hdr-sub">{L["subtitle"]}</p></div>', unsafe_allow_html=True)

st.markdown(f"#### {L['input_header']}")
c1, c2 = st.columns([3, 1])
with c1:
    question = st.text_area("q", placeholder=L["input_ph"], label_visibility="collapsed", height=90)
with c2:
    ex_pick = st.selectbox("ex", [L["pick_example"]] + L["examples_list"],
                           label_visibility="collapsed")
    if ex_pick != L["pick_example"]:
        question = ex_pick

run = st.button(L["run"], type="primary")

if run:
    if not question.strip():
        st.warning(L["empty_warn"]); st.stop()

    st.markdown(f'<div class="stage-label">{L["s1"]}</div>', unsafe_allow_html=True)
    hits = match_glossary(question)
    if hits:
        st.markdown("".join(f'<span class="chip"><b>{t}</b> → <code>{r}</code></span>'
                            for t, r in hits), unsafe_allow_html=True)
    else:
        st.caption(L["s1_none"])

    prompt = build_prompt(method, question)
    with st.expander(L["s2"]):
        st.code(prompt, language=None)

    st.markdown(f'<div class="stage-label">{L["s3"]} — {model_name} × {METHOD_NAMES[method]}</div>',
                unsafe_allow_html=True)
    try:
        client = LLMClient(model_name, cfg["models"][model_name], cfg["generation"])
    except RuntimeError as e:
        st.error(f"{L['init_fail']}：{e}"); st.stop()
    with st.spinner(L["spinner"]):
        resp = client.generate(prompt)
    if resp["error"]:
        st.error(f"{L['api_fail']}：{resp['error']}"); st.stop()

    parsed = parse_model_output(resp["text"])
    if parsed.get("schema_links"):
        st.markdown(f"**{L['sl_map']}**")
        st.dataframe(pd.DataFrame(parsed["schema_links"]), use_container_width=True, hide_index=True)
    if parsed.get("reasoning"):
        st.markdown(f"**{L['reasoning']}**")
        st.info(parsed["reasoning"])
    st.code(parsed.get("sql", ""), language="sql")

    st.markdown(f'<div class="stage-label">{L["s4"]}</div>', unsafe_allow_html=True)
    v = validate_sql(parsed.get("sql", ""))
    if v["ok"]:
        st.markdown(f'<span class="stamp">✓ {L["safe_ok"]}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="stamp blk">✕ {L["safe_block"]}: {v["reason"]}</span>',
                    unsafe_allow_html=True)

    if v["ok"]:
        st.markdown(f'<div class="stage-label">{L["s5"]}</div>', unsafe_allow_html=True)
        try:
            conn = sqlite3.connect(DB_PATH)
            dfr = pd.read_sql_query(v["sql"], conn)
            conn.close()
            st.dataframe(dfr, use_container_width=True)
            st.caption(f"{len(dfr)} {L['result_rows']}")
        except Exception as e:
            st.error(f"{L['exec_fail']}：{e}")

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(L["metric_lat"], f"{resp['latency']:.2f} s")
    m2.metric(L["metric_in"], resp["input_tokens"])
    m3.metric(L["metric_out"], resp["output_tokens"])
    m4.metric(L["metric_method"], METHOD_NAMES[method])

st.markdown(f'<div class="foot">{L["footer"]}</div>', unsafe_allow_html=True)
