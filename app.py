import math
import io
import json
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st
from google import genai
from google.genai import types

# ── API Key Hardcoded Directly ───────────────────────────────────────────────
GEMINI_API_KEY = "AQ.Ab8RN6IiXqXN1mv3GbIU4kr_XPIQI-_MnLP5Occz0FP46XjKeQ"

st.set_page_config(
    page_title="Attendance Planner | Vedant Khilare",
    page_icon="🎓",
    layout="wide",
)

st.markdown("""
<style>
    .card { background:#1e1e2e; border-radius:12px; padding:1.2rem 1.5rem; margin-bottom:0.8rem; border-left:5px solid #7c3aed; }
    .card-safe   { border-left-color:#22c55e; }
    .card-warn   { border-left-color:#f59e0b; }
    .card-danger { border-left-color:#ef4444; }
    .progress-bg { background:#334155; border-radius:99px; height:14px; width:100%; margin-top:6px; }
    .progress-fill { height:14px; border-radius:99px; }
    .tag { display:inline-block; padding:2px 10px; border-radius:99px; font-size:0.75rem; font-weight:600; margin-left:8px; }
    .tag-th { background:#3b82f6; color:#fff; }
    .tag-pr { background:#8b5cf6; color:#fff; }
    .section-header { font-size:1.3rem; font-weight:700; margin:1.5rem 0 0.8rem; border-bottom:2px solid #334155; padding-bottom:6px; }
    .summary-box { background:#0f172a; border-radius:12px; padding:1rem 1.5rem; margin-bottom:1rem; }
</style>
""", unsafe_allow_html=True)

st.title("🎓 MIT-WPU Attendance & Bunk Planner")
st.caption("Upload your ERP screenshot → values auto-fill instantly")

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ University Policy")
min_req      = st.sidebar.slider("Minimum Required Attendance (%)", 50, 95, 80, step=5)
target_ratio = min_req / 100
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Semester Info")
total_weeks     = st.sidebar.number_input("Total Semester Weeks", 1, 26, 16)
current_week    = st.sidebar.number_input("Current Week", 1, int(total_weeks), 8)
weeks_remaining = total_weeks - current_week
st.sidebar.markdown(f"📆 **Weeks Remaining:** {weeks_remaining}")
st.sidebar.info(f"💡 Minimum {min_req}% aggregate required for end-term eligibility.")

# ── Default empty table ───────────────────────────────────────────────────────
if "attendance_df" not in st.session_state:
    st.session_state.attendance_df = pd.DataFrame({
        "Subject":        ["— upload screenshot to auto-fill —"],
        "Type":           ["TH"],
        "Present":        [0],
        "Total Period":   [0],
        "Future Classes": [0],
    })

# ── IMAGE UPLOAD + AI EXTRACTION ─────────────────────────────────────────────
st.markdown('<div class="section-header">📸 Upload ERP Screenshot</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Upload your ERP attendance screenshot (PNG / JPG)",
    type=["png", "jpg", "jpeg"]
)

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Your ERP Screenshot", use_container_width=True)

    if st.button("🔍 Extract Attendance from Image", type="primary"):
        with st.spinner("Reading your attendance data using Gemini…"):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)

                prompt = """This is a university ERP attendance screenshot.
Extract ONLY the subject-wise rows (ignore summary rows like Theory/Practical/Tutorial/Total).

Return a valid JSON array of objects with the following keys:
- "subject": course name (string)
- "type": either "TH" or "PR" (string)
- "present": attended classes (integer)
- "total": total conducted periods (integer)

Do not include markdown fences, code blocks, or explanatory text."""

                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=[img, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                parsed = json.loads(response.text.strip())

                rows = []
                for item in parsed:
                    rows.append({
                        "Subject":        item.get("subject", "Unknown"),
                        "Type":           str(item.get("type", "TH")).upper(),
                        "Present":        int(item.get("present", 0)),
                        "Total Period":   int(item.get("total", 0)),
                        "Future Classes": 0,
                    })

                st.session_state.attendance_df = pd.DataFrame(rows)
                st.success(f"✅ Extracted {len(rows)} subjects successfully!")
                st.rerun()

            except Exception as e:
                st.error(f"Extraction failed: {e}")
                st.info("Check if your API key is valid or try a clearer screenshot.")

# ── Editable Table ────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Attendance Data</div>', unsafe_allow_html=True)
st.caption("Auto-filled from your screenshot · Double-click any cell to edit manually")

edited_df = st.data_editor(
    st.session_state.attendance_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Type":           st.column_config.SelectboxColumn("Type", options=["TH", "PR"], required=True),
        "Present":        st.column_config.NumberColumn("Present", min_value=0),
        "Total Period":   st.column_config.NumberColumn("Total Classes", min_value=0),
        "Future Classes": st.column_config.NumberColumn("Est. Future Classes", min_value=0,
                                                         help="Expected upcoming classes for projection"),
    }
)
st.session_state.attendance_df = edited_df

# ── Calculation Engine ────────────────────────────────────────────────────────
results = []
for _, row in edited_df.iterrows():
    subject    = str(row.get("Subject", "Course"))
    sub_type   = str(row.get("Type", "TH"))
    future_cls = int(row.get("Future Classes", 0) or 0)

    try:
        attended = int(row.get("Present", 0) or 0)
        total    = int(row.get("Total Period", 0) or 0)
    except (ValueError, TypeError):
        attended, total = 0, 0

    if total <= 0:
        results.append({"Subject": subject, "Type": sub_type, "Present": 0, "Total": 0,
                        "Current %": None, "Status": "no_data", "Safe Bunks": 0,
                        "Recovery": 0, "Projected %": None, "Future": future_cls})
        continue

    attended   = min(attended, total)
    pct        = (attended / total) * 100
    safe_bunks = max(0, math.floor((attended - target_ratio * total) / target_ratio)) if target_ratio < 1 else 0
    recovery   = max(0, math.ceil((target_ratio * total - attended) / (1 - target_ratio))) if (pct < min_req and target_ratio < 1) else 0
    proj_pct   = ((attended + future_cls) / (total + future_cls) * 100) if (total + future_cls) > 0 else pct
    status     = ("safe" if safe_bunks > 0 else "borderline") if pct >= min_req else "danger"

    results.append({"Subject": subject, "Type": sub_type, "Present": attended, "Total": total,
                    "Current %": round(pct, 2), "Status": status, "Safe Bunks": safe_bunks,
                    "Recovery": recovery, "Projected %": round(proj_pct, 2), "Future": future_cls})

results_df = pd.DataFrame(results)

def pct_color(p):
    if p >= min_req + 5: return "#22c55e"
    if p >= min_req:     return "#f59e0b"
    return "#ef4444"

def agg(df):
    p = int(df["Present"].sum()); t = int(df["Total"].sum())
    return p, t, (p / t * 100 if t > 0 else 0)

valid              = results_df[results_df["Current %"].notna()]
th_p, th_t, th_pct = agg(valid[valid["Type"] == "TH"])
pr_p, pr_t, pr_pct = agg(valid[valid["Type"] == "PR"])
tot_p, tot_t, tot_pct = agg(valid)

# ── Overall Summary ───────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📊 Overall Attendance Summary</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
for col, label, p, t, pct in [(c1, "📘 Theory", th_p, th_t, th_pct),
                               (c2, "🔬 Practical", pr_p, pr_t, pr_pct),
                               (c3, "🎯 Grand Total", tot_p, tot_t, tot_pct)]:
    color = pct_color(pct)
    with col:
        st.markdown(f"""<div class="summary-box">
            <div style="color:#94a3b8;font-size:.85rem">{label}</div>
            <div style="color:{color};font-size:2rem;font-weight:700">{pct:.1f}%</div>
            <div style="color:#cbd5e1">{p} / {t} classes</div>
            <div class="progress-bg"><div class="progress-fill"
                style="width:{min(pct,100):.1f}%;background:{color}"></div></div>
        </div>""", unsafe_allow_html=True)

safe_c = len(valid[valid["Status"] == "safe"])
border_c = len(valid[valid["Status"] == "borderline"])
danger_c = len(valid[valid["Status"] == "danger"])

with c4:
    st.markdown(f"""<div class="summary-box">
        <div style="color:#94a3b8;font-size:.85rem">📋 Subject Status</div>
        <div style="color:#22c55e;font-size:1.1rem">✅ Safe: {safe_c}</div>
        <div style="color:#f59e0b;font-size:1.1rem">⚠️ Borderline: {border_c}</div>
        <div style="color:#ef4444;font-size:1.1rem">🚨 Deficit: {danger_c}</div>
        <div style="color:#cbd5e1;font-size:.85rem;margin-top:4px">Target: {min_req}%</div>
    </div>""", unsafe_allow_html=True)

# ── Eligibility Banner ────────────────────────────────────────────────────────
if tot_t > 0:
    if tot_pct >= min_req:
        can_miss = max(0, math.floor((tot_p - target_ratio * tot_t) / target_ratio)) if target_ratio < 1 else 0
        st.success(f"🎉 **Exam Eligible** — Overall {tot_pct:.2f}% ≥ {min_req}%. You can still skip **{can_miss}** more class(es) overall.")
    else:
        need = max(0, math.ceil((target_ratio * tot_t - tot_p) / (1 - target_ratio))) if target_ratio < 1 else 999
        st.error(f"🚨 **Not Eligible** — Overall {tot_pct:.2f}% < {min_req}%. Attend at least **{need}** consecutive classes to recover.")

# ── Subject Cards ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📚 Subject-Wise Breakdown</div>', unsafe_allow_html=True)

for r in results:
    pct = r["Current %"]; status = r["Status"]; stype = r["Type"]
    card_cls = {"safe": "card-safe", "borderline": "card-warn", "danger": "card-danger"}.get(status, "")
    tag_cls = "tag-th" if stype == "TH" else "tag-pr"

    if status == "no_data":
        st.markdown(f"""<div class="card"><b>{r['Subject']}</b>
            <span class="tag {tag_cls}">{stype}</span>
            <span style="color:#64748b;margin-left:8px">No data</span></div>""",
            unsafe_allow_html=True)
        continue

    color = pct_color(pct)
    detail = (f"✅ Can skip <b>{r['Safe Bunks']}</b> more class(es)" if status == "safe"
              else "⚠️ At limit — don't miss next class" if status == "borderline"
              else f"🚨 Attend next <b>{r['Recovery']}</b> class(es) to recover")
    proj_str = f"&nbsp;|&nbsp; Projected: <b>{r['Projected %']:.1f}%</b>" if r["Future"] > 0 else ""

    st.markdown(f"""<div class="card {card_cls}">
        <div style="display:flex;justify-content:space-between;align-items:center">
            <div><b style="font-size:1.05rem">{r['Subject']}</b>
                <span class="tag {tag_cls}">{stype}</span></div>
            <div style="color:{color};font-size:1.4rem;font-weight:700">{pct:.1f}%</div>
        </div>
        <div style="color:#94a3b8;font-size:.88rem;margin-top:2px">
            {r['Present']} attended / {r['Total']} total &nbsp;|&nbsp; {detail}{proj_str}
        </div>
        <div class="progress-bg">
            <div class="progress-fill" style="width:{min(pct,100):.1f}%;background:{color}"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:.75rem;color:#475569;margin-top:3px">
            <span>0%</span><span style="color:#f59e0b">{min_req}% required</span><span>100%</span>
        </div>
    </div>""", unsafe_allow_html=True)

# ── Full Results Table ────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Full Results Table</div>', unsafe_allow_html=True)
display_df = results_df[["Subject", "Type", "Present", "Total", "Current %", "Safe Bunks", "Recovery", "Projected %"]].copy()
display_df["Current %"]   = display_df["Current %"].apply(lambda x: f"{x:.2f}%" if x is not None else "N/A")
display_df["Projected %"] = display_df["Projected %"].apply(lambda x: f"{x:.2f}%" if x is not None else "N/A")
st.dataframe(display_df, use_container_width=True)

# ── Bunk Planner ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🗓️ Bunk Planner</div>', unsafe_allow_html=True)
bp_rows = [{"Subject": r["Subject"], "Type": r["Type"],
            "Current %": f"{r['Current %']:.1f}%" if r["Current %"] else "N/A",
            "Can Still Bunk": r["Safe Bunks"],
            "Must Attend to Recover": r["Recovery"]}
           for r in results if r["Status"] != "no_data"]

if bp_rows:
    st.dataframe(pd.DataFrame(bp_rows), use_container_width=True)
    bunk_df = pd.DataFrame([b for b in bp_rows if b["Can Still Bunk"] > 0])
    if not bunk_df.empty:
        st.caption("Safe bunks remaining per subject:")
        st.bar_chart(bunk_df.set_index("Subject")["Can Still Bunk"])

# ── ERP Summary Row ───────────────────────────────────────────────────────────
if tot_t > 0:
    st.markdown('<div class="section-header">📑 ERP-Style Summary</div>', unsafe_allow_html=True)
    erp = pd.DataFrame({
        "Category":     ["Theory", "Practical", "Tutorial", "Total"],
        "Present":      [th_p, pr_p, 0, tot_p],
        "Total Period": [th_t, pr_t, 0, tot_t],
        "Percentage":   [f"{th_pct:.2f}%", f"{pr_pct:.2f}%", "0%", f"{tot_pct:.2f}%"]
    })
    st.dataframe(erp, use_container_width=True, hide_index=True)

# ── Projection Simulator ──────────────────────────────────────────────────────
st.markdown('<div class="section-header">🔮 Projection Simulator</div>', unsafe_allow_html=True)
st.caption("What if you attend X out of the next Y classes?")
s1, s2 = st.columns(2)
with s1: sim_attend = st.number_input("Classes you WILL attend", 0, 500, 10)
with s2: sim_total  = st.number_input("Total upcoming classes", 0, 500, 15)

if sim_total > 0 and tot_t > 0:
    new_p = tot_p + sim_attend; new_t = tot_t + sim_total
    new_pct = (new_p / new_t) * 100; color = pct_color(new_pct)
    eligible = "✅ Eligible" if new_pct >= min_req else "🚨 Not Eligible"
    st.markdown(f"""<div class="summary-box" style="text-align:center">
        <div style="color:#94a3b8">Projected Overall Attendance</div>
        <div style="color:{color};font-size:2.5rem;font-weight:700">{new_pct:.2f}%</div>
        <div style="color:#cbd5e1">{new_p} / {new_t} → <b>{eligible}</b></div>
    </div>""", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("<div style='text-align:center;color:#64748b'>Built by <b>🧑🏽‍🎓 Vedant Khilare 🧑🏽‍🎓</b> | School of Mathematics & Statistics, MIT-WPU</div>",
            unsafe_allow_html=True)
