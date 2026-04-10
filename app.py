import streamlit as st
import pandas as pd
import plotly.express as px

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="EEKI-Logistics Dashboard", page_icon="🚜", layout="wide")

# 2. DATA LOADING & STANDARDIZATION
SOURCES = {
    "Production": {"id": "1PQUiIP5yMQfmJwpwy9e4dv4-HgJNDMwCHfc78eaEu5Y", "gid": "0", "skip": []},
    "History of Transplantation": {"id": "1ww52WQi7nV3dD3tm8VaBsqU3BAStAjRFFp45wu7nC_0", "gid": "0", "skip": [0]},
    "Transplantation Detail": {"id": "1_umHB1sa_6i9Df7Vb3G5uun7eckvx-1xpsbctLwJwSA", "gid": "2014608810", "skip": [0, 1]},
    "Farm Details": {"id": "1K4xTZUTRc0v5ZWkJoYgRvhH2AnDuyCevc39-Ip8_A5g", "gid": "557360707", "skip": []},
    "Transportation": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []},
    "Crop & Vendor Analysis": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []}
}

@st.cache_data(ttl=300)
def load_and_clean_data(source_name):
    source = SOURCES[source_name]
    url = f"https://docs.google.com/spreadsheets/d/{source['id']}/export?format=csv&gid={source['gid']}"
    try:
        df = pd.read_csv(url, skiprows=source['skip'], low_memory=False)
        if df.empty: return df
        
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
        
        # ✅ FY LOGIC
        if date_col_detected:
            df['FY'] = df[date_col_detected].apply(
                lambda x: x.year if pd.notnull(x) and x.month >= 4 
                else (x.year - 1 if pd.notnull(x) else None)
            )

        return df
    except Exception as e:
        st.error(f"Error loading {source_name}: {e}")
        return pd.DataFrame()

# SIDEBAR
st.sidebar.title("🚜 EEKI-Logistics Dashboard")
selected_source = st.sidebar.selectbox("📂 Select View", list(SOURCES.keys()))
df = load_and_clean_data(selected_source)

if not df.empty:
    search = st.sidebar.text_input("🔍 Global Search", "").strip().lower()
    filtered_df = df.copy()

    if search:
        mask = df.apply(lambda r: r.astype(str).str.lower().str.contains(search).any(), axis=1)
        filtered_df = df[mask]

    # ✅ FY FILTER
    if 'FY' in df.columns:
        fy_options = sorted(df['FY'].dropna().unique())
        selected_fy = st.sidebar.selectbox("📅 Financial Year", fy_options)
        filtered_df = filtered_df[filtered_df['FY'] == selected_fy]

    # COLUMN DETECTION
    month_col = next((c for c in df.columns if 'month' in c.lower()), None)
    qty_col = next((c for c in df.columns if any(x in c.lower() for x in ['weight','qty'])), None)
    cost_col = next((c for c in df.columns if any(x in c.lower() for x in ['cost','amount'])), None)
    crop_col = next((c for c in df.columns if 'crop' in c.lower()), None)
    vendor_col = next((c for c in df.columns if 'vendor' in c.lower()), None)
    loc_col = next((c for c in df.columns if 'location' in c.lower()), None)

    st.title(f"📊 {selected_source} Dashboard")

    # KPI
    c1,c2,c3 = st.columns(3)
    c1.metric("Records", len(filtered_df))
    if qty_col: c2.metric("Total Qty", f"{filtered_df[qty_col].sum():,.0f}")
    if cost_col: c3.metric("Total Cost", f"₹ {filtered_df[cost_col].sum():,.0f}")

    st.markdown("---")

    # ✅ FULL CROP & VENDOR ANALYSIS (RESTORED)
    if selected_source == "Crop & Vendor Analysis" and cost_col and qty_col:

        # Filters
        f1,f2,f3 = st.columns(3)
        sel_crop = f1.selectbox("Crop", ["All"] + sorted(filtered_df[crop_col].dropna().unique())) if crop_col else "All"
        sel_vendor = f2.selectbox("Vendor", ["All"] + sorted(filtered_df[vendor_col].dropna().unique())) if vendor_col else "All"
        sel_loc = f3.selectbox("Location", ["All"] + sorted(filtered_df[loc_col].dropna().unique())) if loc_col else "All"

        ana_df = filtered_df.copy()
        if sel_crop!="All": ana_df = ana_df[ana_df[crop_col]==sel_crop]
        if sel_vendor!="All": ana_df = ana_df[ana_df[vendor_col]==sel_vendor]
        if sel_loc!="All": ana_df = ana_df[ana_df[loc_col]==sel_loc]

        # Category Summary
        summary = ana_df.groupby([crop_col,vendor_col]).agg({cost_col:'sum',qty_col:'sum'}).reset_index()
        summary['Cost_per_kg'] = summary[cost_col]/summary[qty_col]

        c1,c2 = st.columns(2)

        # BAR
        with c1:
            fig_cost = px.bar(summary, x=crop_col, y='Cost_per_kg', color=vendor_col, text_auto='.2f')
            st.plotly_chart(fig_cost, use_container_width=True)

        # SCATTER (RESTORED)
        with c2:
            fig_scat = px.scatter(summary, x=qty_col, y=cost_col,
                                  size='Cost_per_kg', color=crop_col,
                                  hover_name=vendor_col)
            st.plotly_chart(fig_scat, use_container_width=True)

        st.markdown("---")

        # PIE (RESTORED)
        if loc_col:
            c1,c2 = st.columns(2)

            with c1:
                fig_pie = px.pie(ana_df, values=cost_col, names=loc_col, hole=0.5)
                st.plotly_chart(fig_pie, use_container_width=True)

            with c2:
                loc_sum = ana_df.groupby(loc_col).agg({cost_col:'sum',qty_col:'sum'}).reset_index()
                loc_sum['Cost_per_kg'] = loc_sum[cost_col]/loc_sum[qty_col]

                fig_bar = px.bar(loc_sum, x=loc_col, y='Cost_per_kg',
                                 color='Cost_per_kg', text_auto='.2f')
                st.plotly_chart(fig_bar, use_container_width=True)

    # RAW DATA
    with st.expander("🔍 View Data"):
        st.dataframe(filtered_df)

else:
    st.error("No data")
