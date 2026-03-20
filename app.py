import streamlit as st
import pandas as pd
import plotly.express as px

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="EEKI-Logistics Dashboard", page_icon="🚜", layout="wide")

# 2. DATA LOADING & ROBUST DATE PARSING
SOURCES = {
    "Production": {"id": "1PQUiIP5yMQfmJwpwy9e4dv4-HgJNDMwCHfc78eaEu5Y", "gid": "0", "skip": []},
    "History of Transplantation": {"id": "1ww52WQi7nV3dD3tm8VaBsqU3BAStAjRFFp45wu7nC_0", "gid": "0", "skip": [0]},
    "Transplantation Detail": {"id": "1_umHB1sa_6i9Df7Vb3G5uun7eckvx-1xpsbctLwJwSA", "gid": "2014608810", "skip": [0, 1]},
    "Farm Details": {"id": "1K4xTZUTRc0v5ZWkJoYgRvhH2AnDuyCevc39-Ip8_A5g", "gid": "557360707", "skip": []},
    "Transportation": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []},
    "Crop & Vendor Analysis": {"id": "1thJEWMmb86NQt7Rap992DmbJzpjik1MCF250esi9Qbs", "gid": "0", "skip": []}
}

@st.cache_data(ttl=60)
def load_and_clean_data(source_name):
    source = SOURCES[source_name]
    url = f"https://docs.google.com/spreadsheets/d/{source['id']}/export?format=csv&gid={source['gid']}"
    try:
        # Read everything as strings first to avoid pandas guessing the wrong date format
        df = pd.read_csv(url, skiprows=source['skip'], low_memory=False, dtype=str)
        if df.empty: return df
        
        # Remove completely empty rows
        df = df.dropna(how='all')

        for col in df.columns:
            col_lower = col.lower().strip()
            
            # --- ROBUST DATE PARSING (DD/MM/YYYY) ---
            if 'date' in col_lower:
                # Force dd/mm/yyyy parsing
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
            
            # --- NUMERIC STANDARDIZATION ---
            elif any(x in col_lower for x in ['qty', 'weight', 'area', 'cost', 'amount', 'price']):
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            
            # --- TEXT STANDARDIZATION ---
            else:
                df[col] = df[col].astype(str).str.strip().str.title()
                df[col] = df[col].replace('Nan', None)
        
        return df
    except Exception as e:
        st.error(f"Error loading {source_name}: {e}")
        return pd.DataFrame()

# 3. SIDEBAR NAVIGATION & FILTERS
st.sidebar.title("🚜 EEKI-Logistics Dashboard")
selected_source = st.sidebar.selectbox("📂 Select View", list(SOURCES.keys()))
df = load_and_clean_data(selected_source)

if not df.empty:
    # --- DYNAMIC FILTERS ---
    date_col = next((c for c in df.columns if 'date' in c.lower()), None)
    
    # 3.1 Year Filter
    if date_col:
        df['Year_Helper'] = df[date_col].dt.year
        available_years = sorted(df['Year_Helper'].dropna().unique().astype(int).tolist(), reverse=True)
        if available_years:
            sel_year = st.sidebar.selectbox("📅 Select Year", ["All Years"] + available_years)
            if sel_year != "All Years":
                df = df[df['Year_Helper'] == sel_year]

    # 3.2 Month Filter (Financial Year Order)
    month_names = ['April', 'May', 'June', 'July', 'August', 'September', 
                   'October', 'November', 'December', 'January', 'February', 'March']
    sel_months = st.sidebar.multiselect("🗓️ Filter Months", month_names, default=month_names)

    # Global Search
    search = st.sidebar.text_input("🔍 Search Anything", "").strip().lower()
    
    # Apply Filtering
    filtered_df = df.copy()
    if search:
        mask = filtered_df.apply(lambda r: r.astype(str).str.lower().str.contains(search).any(), axis=1)
        filtered_df = filtered_df[mask]

    # Detect Columns for Charts
    month_col = next((c for c in filtered_df.columns if 'month' in c.lower()), None)
    qty_col = next((c for c in filtered_df.columns if any(x in c.lower() for x in ['weight', 'qty', 'total weight'])), None)
    cost_col = next((c for c in filtered_df.columns if any(x in c.lower() for x in ['cost', 'amount', 'total cost'])), None)
    crop_col = next((c for c in filtered_df.columns if any(x in c.lower() for x in ['crop', 'item'])), None)
    vendor_col = next((c for c in filtered_df.columns if any(x in c.lower() for x in ['vendor', 'supplier', 'transporter'])), None)
    loc_col = next((c for c in filtered_df.columns if any(x in c.lower().strip() for x in ['location', 'site', 'destination'])), None)

    # 4. KPI SUMMARY
    st.title(f"📊 {selected_source} Dashboard")
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Records", f"{len(filtered_df):,}")
    if qty_col: k2.metric(f"Total {qty_col}", f"{filtered_df[qty_col].sum():,.0f}")
    if cost_col: k3.metric("Total Expenditure", f"₹ {filtered_df[cost_col].sum():,.0f}")

    st.markdown("---")

    # 5. ANALYSIS VIEWS
    if selected_source in ["Crop & Vendor Analysis", "Transportation"]:
        
        # Prepare data for plotting
        plot_df = filtered_df.copy()
        if date_col:
            plot_df['Display_Month'] = plot_df[date_col].dt.month_name()
        elif month_col:
            plot_df['Display_Month'] = plot_df[month_col].astype(str).str.strip().str.capitalize()
        
        # Filter by selected months
        plot_df = plot_df[plot_df['Display_Month'].isin(sel_months)]
        
        # Sort by Financial Year
        fy_order = {m: i for i, m in enumerate(month_names)}
        plot_df['Month_Sort'] = plot_df['Display_Month'].map(fy_order)
        
        if not plot_df.empty and qty_col:
            st.subheader("📅 Month-on-Month Trend")
            time_agg = plot_df.groupby(['Display_Month', 'Month_Sort'])[qty_col].sum().reset_index().sort_values('Month_Sort')
            
            fig_trend = px.bar(time_agg, x='Display_Month', y=qty_col, 
                               text_auto='.0f', color_discrete_sequence=['#4CAF50'],
                               title=f"Total {qty_col} by Month")
            fig_trend.update_xaxes(categoryorder='array', categoryarray=month_names)
            st.plotly_chart(fig_trend, use_container_width=True)

        # Category Analysis (Specific to Crop & Vendor)
        if selected_source == "Crop & Vendor Analysis" and crop_col and vendor_col:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("💰 Spend by Crop")
                fig_crop = px.pie(plot_df, values=cost_col if cost_col else qty_col, names=crop_col, hole=0.4)
                st.plotly_chart(fig_crop, use_container_width=True)
            with c2:
                st.subheader("🚚 Top Vendors")
                vend_agg = plot_df.groupby(vendor_col)[qty_col].sum().reset_index().sort_values(qty_col, ascending=False).head(10)
                fig_vend = px.bar(vend_agg, x=qty_col, y=vendor_col, orientation='h', color=qty_col)
                st.plotly_chart(fig_vend, use_container_width=True)

    # 6. RAW DATA
    with st.expander("🔍 View All Filtered Raw Data"):
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

else:
    st.error("No data available. Please check the sheet and the date format (DD/MM/YYYY).")
