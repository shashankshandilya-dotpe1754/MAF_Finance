import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ================= PAGE LAYOUT — FULL WIDTH =================
st.set_page_config(layout="wide")

# ================= TABLE AUTO-FIT STYLE =================
st.markdown("""
<style>
table { width: 100% !important; }
thead tr th { white-space: nowrap !important; }
tbody tr td { white-space: nowrap !important; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# GOOGLE SHEETS AUTH
# =====================================================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

json_key_path = r"C:\Users\shashank.shandilya_d\Desktop\Vs Code\boxwood-mantra-456206-s3-bc70dce6a998.json"

creds = ServiceAccountCredentials.from_json_keyfile_name(json_key_path, scope)
client = gspread.authorize(creds)

SHEET_URL = "https://docs.google.com/spreadsheets/d/18Yp4-QNYMP3tPCT5oNw6QnVNu4PraTZuZM3CV1_aLrU/edit"
TAB_NAME = "Upload-RAW"


# =====================================================
# LOAD DATA — SAFE + CLEAN
# =====================================================

@st.cache_data(ttl=300)
def load_data():

    ws = client.open_by_url(SHEET_URL).worksheet(TAB_NAME)
    values = ws.get_all_values()

    headers = values[0]
    rows = values[1:]

    seen = {}
    new_headers = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            new_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            new_headers.append(h)

    df = pd.DataFrame(rows, columns=new_headers)

    df["Total Paid  Amount"] = (
        df["Total Paid  Amount"]
        .astype(str)
        .str.replace("₹", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )
    df["Total Paid  Amount"] = pd.to_numeric(
        df["Total Paid  Amount"], errors="coerce"
    ).fillna(0)

    df["Status"] = df["Status"].str.strip()
    df["Stage (MAFs)"] = df["Stage (MAFs)"].str.strip()
    df["Actual Owner Email Id"] = df["Actual Owner Email Id"].str.strip()

    return df


df = load_data()


# =====================================================
# TOTAL CARDS
# =====================================================

def format_inr(x):
    return f"₹{int(x):,}"

total_active_amt = df.loc[df["Status"] == "Active", "Total Paid  Amount"].sum()
total_inactive_amt = df.loc[df["Status"] == "Inactive", "Total Paid  Amount"].sum()
grand_total_amt = total_active_amt + total_inactive_amt


# =====================================================
# SUMMARY BUILDER (ONLY ZERO-ROW FILTER ADDED)
# =====================================================

def build_summary(input_df):

    g = input_df.groupby("Actual Owner Email Id")

    summary = pd.DataFrame({
        "Active Cases": g.size(),
        "Active Amount": g["Total Paid  Amount"].sum(),
        "Draft": g.apply(lambda x: (x["Stage (MAFs)"] == "Draft").sum()),
        "Draft Amount": g.apply(
            lambda x: x.loc[x["Stage (MAFs)"] == "Draft", "Total Paid  Amount"].sum()
        ),
        "Submitted for Signatures": g.apply(
            lambda x: (x["Stage (MAFs)"] == "Submitted for Signatures").sum()
        ),
        "Submitted Amount": g.apply(
            lambda x: x.loc[
                x["Stage (MAFs)"] == "Submitted for Signatures",
                "Total Paid  Amount"
            ].sum()
        ),
        "Information Missing": g.apply(
            lambda x: (x["Stage (MAFs)"] == "Information Missing").sum()
        ),
        "Information Missing Amount": g.apply(
            lambda x: x.loc[
                x["Stage (MAFs)"] == "Information Missing",
                "Total Paid  Amount"
            ].sum()
        ),
    }).reset_index()

    total_row = pd.DataFrame(summary.sum(numeric_only=True)).T
    total_row["Actual Owner Email Id"] = "TOTAL"

    summary = pd.concat([summary, total_row], ignore_index=True)

    # ✅ REMOVE ZERO ROWS (keep TOTAL)
    summary = summary[
        (summary["Actual Owner Email Id"] == "TOTAL") |
        (summary["Active Cases"] > 0)
    ]

    amt_cols = [c for c in summary.columns if "Amount" in c]
    for c in amt_cols:
        summary[c] = summary[c].apply(lambda x: f"₹{int(x):,}")

    return summary.sort_values("Active Cases", ascending=False)


# =====================================================
# UI
# =====================================================

page = st.sidebar.radio("Navigation", ["Summary", "Cases"])


# ================= SUMMARY =================

if page == "Summary":

    st.title("📊 Owner Case Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Active Amount", format_inr(total_active_amt))
    c2.metric("Total Inactive Amount", format_inr(total_inactive_amt))
    c3.metric("Grand Total Amount", format_inr(grand_total_amt))

    st.subheader("✅ Active Cases")
    st.table(build_summary(df[df["Status"] == "Active"]))

    st.subheader("❌ Inactive Cases")
    st.table(build_summary(df[df["Status"] == "Inactive"]))


# ================= CASES =================

if page == "Cases":

    st.title("📁 Cases")

    show_df = df.iloc[:, 0:18].copy()

    status_opts = sorted(df["Status"].unique())
    stage_opts = sorted(df["Stage (MAFs)"].unique())
    month_opts = sorted(df["Month"].unique())
    type_opts = sorted(df["Type"].unique())

    sel_all_status = st.checkbox("Select All Status", value=True)
    status_filter = status_opts if sel_all_status else st.multiselect("Status", status_opts)

    sel_all_stage = st.checkbox("Select All Stage", value=True)
    stage_filter = stage_opts if sel_all_stage else st.multiselect("Stage (MAFs)", stage_opts)

    sel_all_month = st.checkbox("Select All Month", value=True)
    month_filter = month_opts if sel_all_month else st.multiselect("Month", month_opts)

    sel_all_type = st.checkbox("Select All Type", value=True)
    type_filter = type_opts if sel_all_type else st.multiselect("Type", type_opts)

    mask = (
        show_df["Status"].isin(status_filter) &
        show_df["Stage (MAFs)"].isin(stage_filter) &
        show_df["Month"].isin(month_filter) &
        show_df["Type"].isin(type_filter)
    )

    filtered = show_df[mask]

    st.write("Rows:", len(filtered))

    colA, colB = st.columns(2)

    colA.download_button(
        "⬇ Download FULL data (CSV)",
        df.to_csv(index=False),
        file_name="full_cases.csv",
        mime="text/csv"
    )

    colB.download_button(
        "⬇ Download FILTERED data (CSV)",
        filtered.to_csv(index=False),
        file_name="filtered_cases.csv",
        mime="text/csv"
    )

    st.table(filtered)


st.caption("Auto refreshed from Google Sheet")
