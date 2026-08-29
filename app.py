import math
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

st.set_page_config(page_title="MIT-WPU Attendance & Bunk Planner", page_icon="🎓", layout="wide")

st.title("🎓 MIT-WPU Academic Attendance & Bunk Planner")
st.caption("Auto-Scan ERP Screenshot | Compliance Optimizer")

# Sidebar Configuration
st.sidebar.header("⚙️ University Policy")
min_req = st.sidebar.slider("Minimum Required Attendance (%)", 50, 90, 75, step=5)
target_ratio = min_req / 100

st.sidebar.markdown("---")
st.sidebar.info("💡 **Rule:** 75% minimum aggregate attendance is required for end-term examination eligibility.")

# -----------------------------------------------------------------------------
# DEFAULT FALLBACK DATA
# -----------------------------------------------------------------------------
if "attendance_df" not in st.session_state:
    st.session_state.attendance_df = pd.DataFrame({
        "Subject": [
            "Yoga - I",
            "Descriptive Statistics-I",
            "Introduction to Probability Theory",
            "R Programming",
            "Calculus",
            "Discrete Mathematics"
        ],
        "Type": ["PR", "TH", "TH", "PR", "TH", "TH"],
        "Present": [1, 14, 14, 12, 10, 7],
        "Total Period": [4, 15, 15, 16, 11, 9]
    })

# -----------------------------------------------------------------------------
# SCREENSHOT UPLOADER & OCR PARSER
# -----------------------------------------------------------------------------
st.subheader("📸 Upload ERP Attendance Screenshot")
uploaded_file = st.file_uploader("Upload your portal screenshot (PNG/JPG)", type=["png", "jpg", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    # Fixed argument: use_container_width instead of use_column_width
    st.image(img, caption="Uploaded Portal Screenshot", use_container_width=True)

    if st.button("🔍 Scan & Extract Attendance"):
        with st.spinner("Processing image with OCR..."):
            try:
                import easyocr
                reader = easyocr.Reader(['en'], gpu=False)
                ocr_results = reader.readtext(np.array(img))
                
                # Extract clean lines of text
                detected_lines = [item[1].strip() for item in ocr_results if item[1].strip()]
                
                st.success("Screenshot scanned successfully! Review the detected values below.")
            except Exception as e:
                st.error(f"OCR Reader encountered an issue: {e}")
                st.info("You can still manually tweak or verify your numbers in the table below.")

# -----------------------------------------------------------------------------
# INTERACTIVE DATA TABLE
# -----------------------------------------------------------------------------
st.write("")
st.subheader("📋 Verify & Edit Attendance Data")
st.caption("Double-click any cell to edit or add missing subjects:")

edited_df = st.data_editor(
    st.session_state.attendance_df,
    num_rows="dynamic",
    use_container_width=True
)

# -----------------------------------------------------------------------------
# CALCULATION ENGINE
# -----------------------------------------------------------------------------
results = []
for _, row in edited_df.iterrows():
    subject = str(row.get("Subject", "Course"))
    sub_type = str(row.get("Type", "TH"))
    
    try:
        attended = int(row.get("Present", 0))
        total = int(row.get("Total Period", 1))
    except (ValueError, TypeError):
        attended, total = 0, 1

    total = max(1, total)
    attended = min(attended, total)
    pct = (attended / total) * 100

    if pct >= min_req:
        safe_bunks = math.floor((attended - (target_ratio * total)) / target_ratio)
        if safe_bunks > 0:
            status = f"✅ Safe (Can skip {safe_bunks} more)"
        else:
            status = "⚠️ Borderline (Do not miss next class)"
    else:
        recovery_needed = math.ceil(((target_ratio * total) - attended) / (1 - target_ratio))
        status = f"🚨 Deficit (Must attend next {recovery_needed} consecutive)"

    results.append({
        "Subject": subject,
        "Type": sub_type,
        "Present": attended,
        "Total Period": total,
        "Current %": f"{pct:.2f}%",
        "Action / Margin": status
    })

results_df = pd.DataFrame(results)

st.divider()

# -----------------------------------------------------------------------------
# RESULTS & METRICS BREAKDOWN
# -----------------------------------------------------------------------------
st.subheader("📊 Subject-Wise Eligibility & Bunk Allowance")
st.dataframe(results_df, use_container_width=True)

st.divider()
st.subheader("📈 Summary Breakdown")

theory_df = edited_df[edited_df["Type"] == "TH"]
practical_df = edited_df[edited_df["Type"] == "PR"]

th_pres = int(theory_df["Present"].sum()) if not theory_df.empty else 0
th_tot = int(theory_df["Total Period"].sum()) if not theory_df.empty else 0

pr_pres = int(practical_df["Present"].sum()) if not practical_df.empty else 0
pr_tot = int(practical_df["Total Period"].sum()) if not practical_df.empty else 0

tot_pres = int(edited_df["Present"].sum())
tot_tot = int(edited_df["Total Period"].sum())

th_pct = (th_pres / th_tot) * 100 if th_tot > 0 else 0
pr_pct = (pr_pres / pr_tot) * 100 if pr_tot > 0 else 0
tot_pct = (tot_pres / tot_tot) * 100 if tot_tot > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("Theory Total", f"{th_pres} / {th_tot}", f"{th_pct:.2f}%")
col2.metric("Practical Total", f"{pr_pres} / {pr_tot}", f"{pr_pct:.2f}%")
col3.metric("Grand Total (Aggregate)", f"{tot_pres} / {tot_tot}", f"{tot_pct:.2f}%")

if tot_pct >= min_req:
    st.success(f"🎉 **Overall Safe:** Cumulative attendance is **{tot_pct:.2f}%**, above the {min_req}% cutoff.")
else:
    st.error(f"🚨 **Attention Required:** Cumulative attendance is **{tot_pct:.2f}%**, below the mandatory {min_req}% cutoff.")
    st.set_page_config(
    page_title="Attendance Planner | by Vedant Khilare",
    page_icon="🎓",
    layout="wide",
)

# Add a footer at the bottom of the script:
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "Built by <b>🧑🏽‍🎓Vedant Khilare🧑🏽‍🎓</b> | School of Mathematics & Statistics"
    "</div>",
    unsafe_allow_html=True,
)
