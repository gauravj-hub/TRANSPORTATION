import streamlit as st
import pandas as pd
import plotly.express as px

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="EEKI-Logistics Dashboard", page_icon="🚜", layout="wide")

# 2. DATA SOURCES
SOURCES = {
    "Production": {"id": "1PQUiIP5yMQfmJwpwy9e4dv4-HgJNDMwCHfc78eaEu5Y", "gid": "0", "skip": []},
    "History of Transplantation": {"id": "1ww52WQi7nV3dD3tm8VaBsqU3BAStAjRFFp45wu7nC_0", "gid": "0", "skip": [0]},
    "Transplantation Detail": {"id": "1_umHB1sa_6i9Df7Vb3G5uun7eckvx-1xpsbctLwJwSA", "gid": "2014608810", "skip": [0, 1]},
    "Farm Details": {"id": "1K4xTZUTRc0v5ZWkJoYgRvhH2AnDuyCevc39-Ip8_A5g", "gid": "557360707", "skip": []},
    "Transportation": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []},
    "Crop & Vendor Analysis": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []}
}

# 3. LOAD DATA
@st.cache_data(ttl=300)
def load_and_clean_data(source_name):
    source = SOURCES[source_name]
    url = f"https://docs.google.com/spreadsheets/d/{source['id']}/export?format=csv&gid={source['gid']}"

    try:
        df = pd.read_csv(url, skiprows=source['skip'], low_memory=False)
        if df.empty:
            return df

        # Remove blank rows
        df = df[df.iloc[:, 0].notna() & (df.iloc[:, 0].astype(str).str.strip() != "")]

        date_col_detected = None

        for col in df.columns:
            col_lower = col.lower()

            # Clean text
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.title()

            # Detect & convert date
            if 'date' in col_lower:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                date_col_detected = col

            # Numeric cleanup
            if any(x in col_lower for x in ['qty', 'weight', 'area', 'cost', 'amount', 'price']):
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')

        # ✅ Financial Year Logic (April → March)
        if date_col_detected:
            df['FY'] = df[date_col_detected].apply(
                lambda x: x.year if pd.notnull(x) and x.month >= 4 else (x.year - 1 if pd.notnull(x) else None)
            )

        return df

    except Exception as e:
        st.error(f"Error loading {source_name}: {e}")
        return pd.DataFrame()


# 4. SIDEBAR
st.sidebar.title("🚜 EEKI-Logistics Dashboard")
selected_source = st.sidebar.selectbox("📂 Select View", list(SOURCES.keys()))

df = load_and_clean_data(selected_source)

if not df.empty:

    # 🔍 Global Search
    search = st.sidebar.text_input("🔍 Global Search").strip().lower()
    filtered_df = df.copy()

    if search:
        mask = df.apply(lambda r: r.astype(str).str.lower().str.contains(search).any(), axis=1)
        filtered_df = df[mask]

    # 📅 Financial Year Filter
    if 'FY' in df.columns:
        fy_options = sorted(df['FY'].dropna().unique())
        selected_fy = st.sidebar.selectbox("📅 Select Financial Year", fy_options)

        filtered_df = filtered_df[filtered_df['FY'] == selected_fy]

    # COLUMN DETECTION
    date_col = next((c for c in df.columns if 'date' in c.lower()), None)
    month_col = next((c for c in df.columns if 'month' in c.lower()), None)
    qty_col = next((c for c in df.columns if any(x in c.lower() for x in ['weight', 'qty'])), None)
    cost_col = next((c for c in df.columns if any(x in c.lower() for x in ['cost', 'amount'])), None)
    crop_col = next((c for c in df.columns if 'crop' in c.lower()), None)
    vendor_col = next((c for c in df.columns if any(x in c.lower() for x in ['vendor', 'supplier'])), None)
    loc_col = next((c for c in df.columns if any(x in c.lower() for x in ['location', 'site'])), None)

    # TITLE
    st.title(f"📊 {selected_source} Dashboard")

    # KPI
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Records", f"{len(filtered_df):,}")
    with c2:
        if qty_col:
            st.metric("Total Quantity", f"{filtered_df[qty_col].sum():,.0f}")
    with c3:
        if cost_col:
            st.metric("Total Cost", f"₹ {filtered_df[cost_col].sum():,.0f}")

    st.markdown("---")

    # 📊 MONTH SORT (April → March)
    if month_col and qty_col:
        fy_order = {
            'April': 1, 'May': 2, 'June': 3, 'July': 4,
            'August': 5, 'September': 6, 'October': 7,
            'November': 8, 'December': 9,
            'January': 10, 'February': 11, 'March': 12
        }

        temp_df = filtered_df.copy()
        temp_df[month_col] = temp_df[month_col].astype(str).str.strip().str.capitalize()
        temp_df['Month_Sort'] = temp_df[month_col].map(fy_order)
        temp_df = temp_df.dropna(subset=['Month_Sort'])

        agg = temp_df.groupby([month_col, 'Month_Sort'])[qty_col].sum().reset_index()
        agg = agg.sort_values('Month_Sort')

        fig = px.bar(
            agg,
            x=month_col,
            y=qty_col,
            text_auto=',.0f',
            color=qty_col,
            color_continuous_scale='Greens',
            title="Monthly Performance (Financial Year)"
        )

        fig.update_xaxes(categoryorder='array', categoryarray=list(fy_order.keys()))
        st.plotly_chart(fig, use_container_width=True)

    # 📋 RAW DATA
    with st.expander("🔍 View Data"):
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

else:
    st.error("No data available")
