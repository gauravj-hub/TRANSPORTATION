import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="EEKI-Logistics Dashboard", page_icon="🚜", layout="wide")

# -----------------------------
# SOURCES
# -----------------------------
SOURCES = {
    "Production": {"id": "1PQUiIP5yMQfmJwpwy9e4dv4-HgJNDMwCHfc78eaEu5Y", "gid": "0", "skip": []},
    "History of Transplantation": {"id": "1ww52WQi7nV3dD3tm8VaBsqU3BAStAjRFFp45wu7nC_0", "gid": "0", "skip": [0]},
    "Transplantation Detail": {"id": "1_umHB1sa_6i9Df7Vb3G5uun7eckvx-1xpsbctLwJwSA", "gid": "2014608810", "skip": [0, 1]},
    "Farm Details": {"id": "1K4xTZUTRc0v5ZWkJoYgRvhH2AnDuyCevc39-Ip8_A5g", "gid": "557360707", "skip": []},
    "Transportation": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []},
    "Crop & Vendor Analysis": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []}
}

# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data(ttl=300)
def load_and_clean_data(source_name):
    source = SOURCES[source_name]
    url = f"https://docs.google.com/spreadsheets/d/{source['id']}/export?format=csv&gid={source['gid']}"

    df = pd.read_csv(url, skiprows=source['skip'], low_memory=False)

    df = df[df.iloc[:, 0].notna() & (df.iloc[:, 0].astype(str).str.strip() != "")]

    date_col = None

    for col in df.columns:
        c = col.lower()

        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip().str.title()

        if "date" in c:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            date_col = col

        if any(x in c for x in ["qty", "weight"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if any(x in c for x in ["cost", "amount", "price"]):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if date_col:
        df["FY"] = df[date_col].apply(
            lambda x: x.year if pd.notnull(x) and x.month >= 4 else (x.year - 1 if pd.notnull(x) else None)
        )

    return df


# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.title("🚜 EEKI Dashboard")

source = st.sidebar.selectbox("Select View", list(SOURCES.keys()))
df = load_and_clean_data(source)

if not df.empty:

    search = st.sidebar.text_input("Search").lower()
    filtered_df = df.copy()

    if search:
        filtered_df = df[df.apply(lambda r: r.astype(str).str.lower().str.contains(search).any(), axis=1)]

    # FY FILTER
    if "FY" in df.columns:
        fy = st.sidebar.selectbox("FY", sorted(df["FY"].dropna().unique()))
        filtered_df = filtered_df[filtered_df["FY"] == fy]

    # COLUMN DETECTION
    month_col = next((c for c in df.columns if "month" in c.lower()), None)
    qty_col = next((c for c in df.columns if "weight" in c.lower() or "qty" in c.lower()), None)
    cost_col = next((c for c in df.columns if "cost" in c.lower()), None)
    crop_col = next((c for c in df.columns if "crop" in c.lower()), None)
    vendor_col = next((c for c in df.columns if "vendor" in c.lower()), None)
    loc_col = next((c for c in df.columns if "location" in c.lower()), None)

    st.title(f"📊 {source} Dashboard")

    # =========================
    # KPI → ALWAYS COST/KG
    # =========================
    total_qty = filtered_df[qty_col].sum() if qty_col else 0
    total_cost = filtered_df[cost_col].sum() if cost_col else 0

    cost_per_kg = total_cost / total_qty if total_qty != 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Records", len(filtered_df))
    c2.metric("Total Qty", f"{total_qty:,.0f}")
    c3.metric("Cost / KG", f"₹ {cost_per_kg:.2f}")

    st.markdown("---")

    # =====================================================
    # 🚜 CROP & VENDOR (FULLY DYNAMIC)
    # =====================================================
    if source == "Crop & Vendor Analysis" and qty_col:

        f1, f2, f3 = st.columns(3)

        sel_crop = f1.selectbox("Crop", ["All"] + sorted(filtered_df[crop_col].dropna().unique())) if crop_col else "All"
        sel_vendor = f2.selectbox("Vendor", ["All"] + sorted(filtered_df[vendor_col].dropna().unique())) if vendor_col else "All"
        sel_loc = f3.selectbox("Location", ["All"] + sorted(filtered_df[loc_col].dropna().unique())) if loc_col else "All"

        ana = filtered_df.copy()

        if sel_crop != "All":
            ana = ana[ana[crop_col] == sel_crop]
        if sel_vendor != "All":
            ana = ana[ana[vendor_col] == sel_vendor]
        if sel_loc != "All":
            ana = ana[ana[loc_col] == sel_loc]

        # 🔥 DYNAMIC COST/KG (MAIN CHANGE)
        qty = ana[qty_col].sum()
        cost = ana[cost_col].sum()
        cpk = cost / qty if qty != 0 else 0

        st.metric("Cost / KG (Filtered)", f"₹ {cpk:.2f}")

        # MONTH TREND (COST/KG DYNAMIC)
        if month_col:
            fy_order = {
                'April':1,'May':2,'June':3,'July':4,'August':5,'September':6,
                'October':7,'November':8,'December':9,
                'January':10,'February':11,'March':12
            }

            tmp = ana.copy()
            tmp[month_col] = tmp[month_col].astype(str).str.strip().str.capitalize()
            tmp["sort"] = tmp[month_col].map(fy_order)

            m = tmp.groupby([month_col,"sort"]).agg({qty_col:"sum",cost_col:"sum"}).reset_index()
            m = m.sort_values("sort")
            m["Cost/KG"] = m[cost_col] / m[qty_col]

            c1, c2 = st.columns(2)

            with c1:
                st.plotly_chart(px.bar(m, x=month_col, y=qty_col, title="Monthly Weight"), use_container_width=True)

            with c2:
                st.plotly_chart(px.line(m, x=month_col, y="Cost/KG", title="Cost/KG Trend"), use_container_width=True)

    # =====================================================
    # 🚚 TRANSPORT (DYNAMIC COST/KG)
    # =====================================================
    elif source == "Transportation" and qty_col:

        qty = filtered_df[qty_col].sum()
        cost = filtered_df[cost_col].sum() if cost_col else 0
        cpk = cost / qty if qty != 0 else 0

        st.metric("Cost / KG", f"₹ {cpk:.2f}")

        if month_col:
            fy_order = {
                'April':1,'May':2,'June':3,'July':4,'August':5,'September':6,
                'October':7,'November':8,'December':9,
                'January':10,'February':11,'March':12
            }

            tmp = filtered_df.copy()
            tmp[month_col] = tmp[month_col].astype(str).str.strip().str.capitalize()
            tmp["sort"] = tmp[month_col].map(fy_order)

            m = tmp.groupby([month_col,"sort"])[qty_col].sum().reset_index()
            m = m.sort_values("sort")

            st.plotly_chart(px.bar(m, x=month_col, y=qty_col, title="Monthly Weight"), use_container_width=True)

    # RAW DATA
    with st.expander("Raw Data"):
        st.dataframe(filtered_df, use_container_width=True)

else:
    st.error("No data")
