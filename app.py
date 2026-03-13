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
        
        # Remove empty rows
        df = df[df.iloc[:, 0].notna() & (df.iloc[:, 0].astype(str).str.strip() != "")]

        for col in df.columns:
            col_lower = col.lower()
            
            # Fix Text Columns (Standardize to Title Case)
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.title()
            
            # Fix Dates
            if 'date' in col_lower:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
            
            # Fix Numbers
            if any(x in col_lower for x in ['qty', 'weight', 'area', 'cost', 'amount', 'price']):
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Error loading {source_name}: {e}")
        return pd.DataFrame()

# 3. SIDEBAR NAVIGATION
st.sidebar.title("🚜 EEKI-Logistics Dashboard")
selected_source = st.sidebar.selectbox("📂 Select View", list(SOURCES.keys()))
df = load_and_clean_data(selected_source)

if not df.empty:
    # GLOBAL SEARCH
    search = st.sidebar.text_input("🔍 Global Search (Case Insensitive)", "").strip().lower()
    filtered_df = df.copy()
    if search:
        mask = df.apply(lambda r: r.astype(str).str.lower().str.contains(search).any(), axis=1)
        filtered_df = df[mask]

    # COLUMN DETECTION
    date_col = next((c for c in df.columns if 'date' in c.lower()), None)
    month_col = next((c for c in df.columns if 'month' in c.lower()), None)
    qty_col = next((c for c in df.columns if any(x in c.lower() for x in ['weight', 'qty', 'total weight'])), None)
    cost_col = next((c for c in df.columns if any(x in c.lower() for x in ['cost', 'amount', 'total cost'])), None)
    crop_col = next((c for c in df.columns if any(x in c.lower() for x in ['crop', 'item'])), None)
    vendor_col = next((c for c in df.columns if any(x in c.lower() for x in ['vendor', 'supplier', 'transporter'])), None)
    loc_col = next((c for c in df.columns if any(x in c.lower().strip() for x in ['location', 'site', 'destination'])), None)
    area_col = next((c for c in df.columns if 'area' in c.lower()), None)

    # 4. KPI SUMMARY
    st.title(f"📊 {selected_source} Dashboard")
    k1, k2, k3 = st.columns(3)
    with k1: st.metric("Total Records", f"{len(filtered_df):,}")
    with k2:
        val_col = qty_col if qty_col else area_col
        if val_col: st.metric(f"Total {val_col}", f"{filtered_df[val_col].sum():,.0f}")
    with k3:
        if cost_col: st.metric("Total Expenditure", f"₹ {filtered_df[cost_col].sum():,.0f}")
        else: st.metric("Data Quality", "Standardized")

    st.markdown("---")

    # 5. ANALYSIS VIEWS
    
    # --- CROP & VENDOR ANALYSIS ---

    if selected_source == "Crop & Vendor Analysis":

        if cost_col and qty_col:

            # --- FILTERS ---

            f1, f2, f3 = st.columns(3)

            with f1:

                crop_opts = ["All Crops"] + sorted(filtered_df[crop_col].dropna().unique().tolist()) if crop_col else ["N/A"]

                sel_crop = st.selectbox("Select Crop", crop_opts)

            with f2:

                vendor_opts = ["All Vendors"] + sorted(filtered_df[vendor_col].dropna().unique().tolist()) if vendor_col else ["N/A"]

                sel_vendor = st.selectbox("Select Vendor", vendor_opts)

            with f3:

                loc_opts = ["All Locations"] + sorted(filtered_df[loc_col].dropna().unique().tolist()) if loc_col else ["N/A"]

                sel_loc = st.selectbox("Select Location", loc_opts)



            ana_df = filtered_df.copy()

            if sel_crop != "All Crops": ana_df = ana_df[ana_df[crop_col] == sel_crop]

            if sel_vendor != "All Vendors": ana_df = ana_df[ana_df[vendor_col] == sel_vendor]

            if sel_loc != "All Locations": ana_df = ana_df[ana_df[loc_col] == sel_loc]



            # --- PART 1: MoM TRENDS ---

            if month_col:

                st.subheader("📅 Month-on-Month Trends (Financial Year)")

                fy_order = {'April': 1, 'May': 2, 'June': 3, 'July': 4, 'August': 5, 'September': 6,

                            'October': 7, 'November': 8, 'December': 9, 'January': 10, 'February': 11, 'March': 12}

               

                trend_df = ana_df.copy()

                trend_df[month_col] = trend_df[month_col].astype(str).str.strip().str.capitalize()

                trend_df['Month_Sort'] = trend_df[month_col].map(fy_order)

               

                mo_agg = trend_df.groupby([month_col, 'Month_Sort']).agg({cost_col: 'sum', qty_col: 'sum'}).reset_index().sort_values('Month_Sort')

                mo_agg['Cost_per_kg'] = (mo_agg[cost_col] / mo_agg[qty_col]).fillna(0)



                m1, m2 = st.columns(2)

                with m1:

                    fig_mo_qty = px.bar(mo_agg, x=month_col, y=qty_col, title=f"Total {qty_col} by Month", text_auto='.0f', color_discrete_sequence=['#4CAF50'])

                    fig_mo_qty.update_xaxes(categoryorder='array', categoryarray=list(fy_order.keys()))

                    st.plotly_chart(fig_mo_qty, use_container_width=True)

                with m2:

                    fig_mo_cpk = px.line(mo_agg, x=month_col, y='Cost_per_kg', title="Avg Cost/Kg Trend", markers=True, text=mo_agg['Cost_per_kg'].apply(lambda x: f"₹{x:.2f}"), color_discrete_sequence=['#FF5722'])

                    fig_mo_cpk.update_xaxes(categoryorder='array', categoryarray=list(fy_order.keys()))

                    st.plotly_chart(fig_mo_cpk, use_container_width=True)

                st.markdown("---")



            # --- PART 2: CATEGORY ANALYSIS ---

            group_keys = [k for k in [crop_col, vendor_col] if k]

            if group_keys:

                summary = ana_df.groupby(group_keys).agg({cost_col: 'sum', qty_col: 'sum'}).reset_index()

                summary['Cost_per_kg'] = (summary[cost_col] / summary[qty_col]).fillna(0)



                c1, c2 = st.columns(2)

                with c1:

                    st.subheader("💰 Cost per KG by Category")

                    fig_cost = px.bar(summary, x=crop_col if crop_col else vendor_col, y='Cost_per_kg', color=vendor_col if vendor_col else None, text_auto='.2f', barmode='group')

                    st.plotly_chart(fig_cost, use_container_width=True)

                with c2:

                    st.subheader("📊 Spend vs Weight Distribution")

                    fig_scat = px.scatter(summary, x=qty_col, y=cost_col, size='Cost_per_kg', color=crop_col if crop_col else None, hover_name=vendor_col)

                    st.plotly_chart(fig_scat, use_container_width=True)

                st.markdown("---")



            # --- PART 3: LOCATION PERFORMANCE ---

            if loc_col:

                st.subheader("📍 Location Performance")

                lc1, lc2 = st.columns(2)

                with lc1:

                    fig_pie = px.pie(ana_df, values=cost_col, names=loc_col, hole=0.5, title="Expenditure Share by Location")

                    st.plotly_chart(fig_pie, use_container_width=True)

                with lc2:

                    loc_sum = ana_df.groupby(loc_col).agg({cost_col: 'sum', qty_col: 'sum'}).reset_index()

                    loc_sum['Cost_per_kg'] = (loc_sum[cost_col] / loc_sum[qty_col]).fillna(0)

                    fig_loc_bar = px.bar(loc_sum, x=loc_col, y='Cost_per_kg', color='Cost_per_kg', text_auto='.2f', title="Avg Cost/Kg by Location", color_continuous_scale='RdYlGn_r')

                    st.plotly_chart(fig_loc_bar, use_container_width=True)



        else:

            st.warning("Ensure Cost and Weight columns exist.")

    # --- TRANSPORTATION PERFORMANCE (April to March Financial Year Sort) ---
    elif selected_source == "Transportation":
        if month_col and qty_col:
            st.subheader("📅 Monthly Performance (Financial Year: Apr - Mar)")
            df_temp = filtered_df.copy()

            # Clean month names to ensure they match dictionary keys
            df_temp[month_col] = df_temp[month_col].astype(str).str.strip().str.capitalize()

            # Define Financial Year Order (April = 1)
            fy_order = {
                'April': 1, 'May': 2, 'June': 3, 'July': 4, 'August': 5, 'September': 6,
                'October': 7, 'November': 8, 'December': 9, 'January': 10, 'February': 11, 'March': 12
            }

            # Map the sort order and remove invalid months
            df_temp['Month_Sort'] = df_temp[month_col].map(fy_order)
            df_temp = df_temp.dropna(subset=['Month_Sort'])

            # Aggregate
            time_agg = df_temp.groupby([month_col, 'Month_Sort'])[qty_col].sum().reset_index()
            time_agg = time_agg.sort_values('Month_Sort')

            # Chart
            fig_time = px.bar(time_agg, x=month_col, y=qty_col, text_auto=',.0f',
                             color=qty_col, color_continuous_scale='Greens',
                             title=f"Total {qty_col} by Month")
            
            # Force X-Axis to maintain the April-March sequence
            fig_time.update_xaxes(categoryorder='array', categoryarray=list(fy_order.keys()))
            st.plotly_chart(fig_time, use_container_width=True)
        else:
            st.warning("Ensure the sheet has a 'Month' column and a 'Weight/Qty' column.")

    # 6. RAW DATA
    with st.expander("🔍 View Filtered Raw Data"):
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

else:
    st.error("No data available. Please check your Google Sheet IDs and permissions.")

