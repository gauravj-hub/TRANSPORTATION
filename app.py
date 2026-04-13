import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(page_title="EEKI-Logistics Dashboard", page_icon="🚜", layout="wide")

# -----------------------------
# INDIAN NUMBER FORMAT (CORE)
# -----------------------------
def format_indian_number(num):
    if pd.isnull(num):
        return ""

    try:
        num = float(num)
    except:
        return str(num)

    s = f"{num:.2f}"
    whole, decimal = s.split(".")

    if len(whole) <= 3:
        return whole + "." + decimal

    last3 = whole[-3:]
    rest = whole[:-3]

    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)

    return ",".join(parts) + "," + last3 + "." + decimal


def format_df_indian(df):
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].apply(format_indian_number)
    return df


# -----------------------------
# DATA SOURCES
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

    try:
        df = pd.read_csv(url, skiprows=source['skip'], low_memory=False)

        if df.empty:
            return df

        df = df[df.iloc[:, 0].notna() & (df.iloc[:, 0].astype(str).str.strip() != "")]

        date_col_detected = None

        for col in df.columns:
            col_lower = col.lower()

            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.title()

            if 'date' in col_lower:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                date_col_detected = col

            if any(x in col_lower for x in ['qty', 'weight', 'area', 'cost', 'amount', 'price']):
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')

        if date_col_detected:
            df['FY'] = df[date_col_detected].apply(
                lambda x: x.year if pd.notnull(x) and x.month >= 4 else (x.year - 1 if pd.notnull(x) else None)
            )

        return df

    except Exception as e:
        st.error(f"Error loading {source_name}: {e}")
        return pd.DataFrame()


# -----------------------------
# KPI ALERT
# -----------------------------
def detect_high_cost_months(df, month_col, value_col):
    if not month_col or not value_col:
        return None, None

    fy_order = {
        'April': 1,'May': 2,'June': 3,'July': 4,'August': 5,'September': 6,
        'October': 7,'November': 8,'December': 9,
        'January': 10,'February': 11,'March': 12
    }

    temp = df.copy()
    temp[month_col] = temp[month_col].astype(str).str.strip().str.capitalize()
    temp['Month_Sort'] = temp[month_col].map(fy_order)
    temp = temp.dropna(subset=['Month_Sort'])

    monthly = temp.groupby(month_col)[value_col].sum().reset_index()

    if monthly.empty:
        return monthly, None

    mean = monthly[value_col].mean()
    std = monthly[value_col].std()

    threshold = mean + 1.5 * std

    alerts = monthly[monthly[value_col] > threshold].sort_values(value_col, ascending=False)

    return monthly, alerts


# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.title("🚜 EEKI-Logistics Dashboard")
selected_source = st.sidebar.selectbox("📂 Select View", list(SOURCES.keys()))

df = load_and_clean_data(selected_source)

if not df.empty:

    search = st.sidebar.text_input("🔍 Global Search", "").strip().lower()
    filtered_df = df.copy()

    if search:
        mask = df.apply(lambda r: r.astype(str).str.lower().str.contains(search).any(), axis=1)
        filtered_df = df[mask]

    if 'FY' in df.columns:
        fy_options = sorted(df['FY'].dropna().unique())
        selected_fy = st.sidebar.selectbox("📅 Financial Year", fy_options)
        filtered_df = filtered_df[filtered_df['FY'] == selected_fy]

    month_col = next((c for c in df.columns if 'month' in c.lower()), None)
    qty_col = next((c for c in df.columns if any(x in c.lower() for x in ['weight','qty'])), None)
    cost_col = next((c for c in df.columns if any(x in c.lower() for x in ['cost','amount'])), None)
    crop_col = next((c for c in df.columns if 'crop' in c.lower()), None)
    vendor_col = next((c for c in df.columns if 'vendor' in c.lower()), None)
    loc_col = next((c for c in df.columns if 'location' in c.lower()), None)

    st.title(f"📊 {selected_source} Dashboard")

    c1,c2,c3 = st.columns(3)
    c1.metric("Records", len(filtered_df))

    if qty_col:
        c2.metric("Total Qty", format_indian_number(filtered_df[qty_col].sum()))

    if cost_col:
        c3.metric("Total Cost", f"₹ {format_indian_number(filtered_df[cost_col].sum())}")

    st.markdown("---")

    # -----------------------------
    # CROP & VENDOR ANALYSIS
    # -----------------------------
    if selected_source == "Crop & Vendor Analysis" and cost_col and qty_col:

        filtered_df = filtered_df[filtered_df[qty_col] > 0]

        f1,f2,f3 = st.columns(3)

        sel_crop = f1.selectbox("Crop", ["All"] + sorted(filtered_df[crop_col].dropna().unique())) if crop_col else "All"
        sel_vendor = f2.selectbox("Vendor", ["All"] + sorted(filtered_df[vendor_col].dropna().unique())) if vendor_col else "All"
        sel_loc = f3.selectbox("Location", ["All"] + sorted(filtered_df[loc_col].dropna().unique())) if loc_col else "All"

        ana_df = filtered_df.copy()

        if sel_crop != "All":
            ana_df = ana_df[ana_df[crop_col] == sel_crop]
        if sel_vendor != "All":
            ana_df = ana_df[ana_df[vendor_col] == sel_vendor]
        if sel_loc != "All":
            ana_df = ana_df[ana_df[loc_col] == sel_loc]

        _, alerts = detect_high_cost_months(ana_df, month_col, cost_col)

        if alerts is not None and not alerts.empty:
            st.warning("⚠️ High Cost Alert")
            st.dataframe(format_df_indian(alerts), use_container_width=True)

        if month_col:
            st.subheader("📅 Monthly Trend")

            fy_order = {
                'April': 1,'May': 2,'June': 3,'July': 4,'August': 5,'September': 6,
                'October': 7,'November': 8,'December': 9,
                'January': 10,'February': 11,'March': 12
            }

            tmp = ana_df.copy()
            tmp[month_col] = tmp[month_col].astype(str).str.strip().str.capitalize()
            tmp['Month_Sort'] = tmp[month_col].map(fy_order)

            mo = tmp.groupby([month_col,'Month_Sort']).agg({qty_col:'sum',cost_col:'sum'}).reset_index()
            mo = mo.sort_values('Month_Sort')

            mo["Qty_Label"] = mo[qty_col].apply(format_indian_number)
            mo["Cost_Label"] = mo[cost_col].apply(format_indian_number)

            c1,c2 = st.columns(2)

            with c1:
                st.plotly_chart(px.bar(mo, x=month_col, y=qty_col, text="Qty_Label"), use_container_width=True)

            with c2:
                st.plotly_chart(px.line(mo, x=month_col, y=cost_col, markers=True), use_container_width=True)

        st.markdown("---")

        summary = ana_df.groupby([crop_col, vendor_col]).agg({cost_col:'sum',qty_col:'sum'}).reset_index()
        summary["Cost_per_Kg"] = summary[cost_col] / summary[qty_col]

        c1,c2 = st.columns(2)

        with c1:
            st.plotly_chart(px.bar(summary, x=crop_col, y="Cost_per_Kg", color=vendor_col), use_container_width=True)

        with c2:
            st.plotly_chart(px.scatter(summary, x=qty_col, y="Cost_per_Kg", color=crop_col), use_container_width=True)

        # Crop-wise Cost/Kg
        crop_summary = ana_df.groupby(crop_col).agg({cost_col:'sum',qty_col:'sum'}).reset_index()
        crop_summary["Cost_per_Kg"] = crop_summary[cost_col] / crop_summary[qty_col]

        st.subheader("🌾 Crop-wise Cost per Kg")
        st.plotly_chart(px.bar(crop_summary, x=crop_col, y="Cost_per_Kg"), use_container_width=True)

        # Location-wise Cost/Kg
        if loc_col:
            loc = ana_df.groupby(loc_col).agg({cost_col:'sum',qty_col:'sum'}).reset_index()
            loc["Cost_per_Kg"] = loc[cost_col] / loc[qty_col]

            st.subheader("📍 Location-wise Cost per Kg")
            st.plotly_chart(px.bar(loc, x=loc_col, y="Cost_per_Kg"), use_container_width=True)

    elif selected_source == "Transportation" and month_col and qty_col:

        st.subheader("📅 Monthly Weight Trend")

        fy_order = {
            'April': 1,'May': 2,'June': 3,'July': 4,'August': 5,'September': 6,
            'October': 7,'November': 8,'December': 9,
            'January': 10,'February': 11,'March': 12
        }

        tmp = filtered_df.copy()
        tmp[month_col] = tmp[month_col].astype(str).str.strip().str.capitalize()
        tmp['Month_Sort'] = tmp[month_col].map(fy_order)
        tmp = tmp.dropna(subset=['Month_Sort'])

        agg = tmp.groupby([month_col,'Month_Sort'])[qty_col].sum().reset_index()
        agg["Qty_Label"] = agg[qty_col].apply(format_indian_number)

        st.plotly_chart(px.bar(agg, x=month_col, y=qty_col, text="Qty_Label"), use_container_width=True)

    with st.expander("🔍 View Data"):
        st.dataframe(format_df_indian(filtered_df), use_container_width=True, hide_index=True)

else:
    st.error("No data available")
