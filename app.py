import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title="College Attendance & Bunk Planner", page_icon="🎓", layout="wide")

st.title("🎓 College Attendance & Bunk Optimizer")
st.caption("Universal Attendance Margin & Compliance Calculator")

# Sidebar Configuration
st.sidebar.header("⚙️ University Policy")
min_req = st.sidebar.slider("Minimum Required Attendance (%)", 50, 95, 80, step=5)
target_ratio = min_req / 100

st.sidebar.markdown("---")
st.sidebar.info(f"💡 Target is currently set to **{min_req}%**.")

# Default placeholder data (generic template)
default_df = pd.DataFrame({
    "Subject": ["Course 1", "Course 2", "Course 3", "Course 4"],
    "Type": ["TH", "TH", "PR", "TH"],
    "Present": [15, 14, 12, 10],
    "Total Period": [15, 15, 16, 11]
})

st.subheader("📋 Enter or Paste Your Attendance")
st.caption("💡 **Tip:** Click any cell to edit, or select the whole table from your ERP and paste it here.")

# Directly edit the DataFrame without session_state dependency
edited_df = st.data_editor(
    default_df,
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
            status = f"✅ Safe (Can skip {safe_bunks} lecture{'s' if safe_bunks != 1 else ''})"
        else:
            status = "⚠️ Borderline (Do not miss next class)"
    else:
        # Avoid floating-point arithmetic glitches
        diff = ((target_ratio * total) - attended) / (1 - target_ratio)
        recovery_needed = math.ceil(round(diff, 5))
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
# RESULTS DISPLAY
# -----------------------------------------------------------------------------
st.subheader("📊 Subject-Wise Eligibility & Bunk Allowance")
st.dataframe(results_df, use_container_width=True)

# Breakdowns
st.divider()
st.subheader("📈 Summary Breakdown")

theory_df = edited_df[edited_df["Type"] == "TH"]
practical_df = edited_df[edited_df["Type"] == "PR"]

th_pres = int(pd.to_numeric(theory_df["Present"], errors="coerce").fillna(0).sum()) if not theory_df.empty else 0
th_tot = int(pd.to_numeric(theory_df["Total Period"], errors="coerce").fillna(1).sum()) if not theory_df.empty else 0

pr_pres = int(pd.to_numeric(practical_df["Present"], errors="coerce").fillna(0).sum()) if not practical_df.empty else 0
pr_tot = int(pd.to_numeric(practical_df["Total Period"], errors="coerce").fillna(1).sum()) if not practical_df.empty else 0

tot_pres = int(pd.to_numeric(edited_df["Present"], errors="coerce").fillna(0).sum())
tot_tot = int(pd.to_numeric(edited_df["Total Period"], errors="coerce").fillna(1).sum())

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
