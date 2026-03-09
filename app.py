import streamlit as st

import pandas as pd

import plotly.express as px



# 1. PAGE CONFIGURATION

st.set_page_config(page_title="EEKI-Logistics Dashboard", page_icon="🚜", layout="wide")



# 2. DATA LOADING & STANDARDIZATION

SOURCES = {

    "Production": {"id": "1PQUiIP5yMQfmJwpwy9e4dv4-HgJNDMwCHfc78eaEu5Y", "gid": "0", "skip": []},

    "History of Transplantation": {"id": "1ww52WQi7nV3dD3tm8VaBsqU3BAStAjRFFp45wu7nC_0", "gid": "0", "skip": []},

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



        for col in df.columns:

            col_lower = col.lower()

           

            # Fix "Noida" vs "noida" (Standardize to Title Case)

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

st.sidebar.title("🚜 Agri-Logistics Dashboard")

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



            group_keys = [k for k in [crop_col, vendor_col, loc_col] if k]

            if group_keys:

                summary = ana_df.groupby(group_keys).agg({cost_col: 'sum', qty_col: 'sum'}).reset_index()

                summary['Cost_per_kg'] = (summary[cost_col] / summary[qty_col]).replace([float('inf')], 0).fillna(0)



                c1, c2 = st.columns(2)

                with c1:

                    st.subheader("💰 Cost per KG Analysis")

                    fig_cost = px.bar(summary, x=crop_col if crop_col else vendor_col, y='Cost_per_kg',

                                     color=vendor_col if vendor_col else None, text_auto='.2f', barmode='group')

                    st.plotly_chart(fig_cost, use_container_width=True)

                with c2:

                    st.subheader("📊 Weight vs Total Spend")

                    fig_scat = px.scatter(summary, x=qty_col, y=cost_col, size='Cost_per_kg',

                                         color=crop_col if crop_col else None, hover_name=vendor_col)

                    # Note: Trendline removed to avoid 'statsmodels' error.

                    # Add trendline="ols" here if statsmodels is installed.

                    st.plotly_chart(fig_scat, use_container_width=True)



                if loc_col:

                    st.markdown("---")

                    st.subheader("📍 Location Performance (Standardized)")

                    lc1, lc2 = st.columns(2)

                    with lc1:

                        fig_pie = px.pie(ana_df, values=cost_col, names=loc_col, hole=0.5, title="Expenditure Share")

                        st.plotly_chart(fig_pie, use_container_width=True)

                    with lc2:

                        loc_sum = ana_df.groupby(loc_col).agg({cost_col: 'sum', qty_col: 'sum'}).reset_index()

                        loc_sum['Cost_per_kg'] = (loc_sum[cost_col] / loc_sum[qty_col]).fillna(0)

                        fig_loc_bar = px.bar(loc_sum, x=loc_col, y='Cost_per_kg', color='Cost_per_kg',

                                           text_auto='.2f', title="Avg Cost/Kg by Location", color_continuous_scale='RdYlGn_r')

                        st.plotly_chart(fig_loc_bar, use_container_width=True)

        else:

            st.warning("Transportation data needs Cost and Weight columns.")



    # --- TRANSPORTATION PERFORMANCE (April to March Sort) ---

    elif selected_source == "Transportation" and date_col and qty_col:

        st.subheader("📅 Monthly Performance (Financial Year: Apr - Mar)")

        df_temp = filtered_df.copy()

        df_temp[date_col] = pd.to_datetime(df_temp[date_col])

       

        # Financial Year Sorting logic

        df_temp['FY_Sort'] = df_temp[date_col].dt.month.map(lambda x: x - 3 if x >= 4 else x + 9)

        df_temp['Year_Sort'] = df_temp[date_col].dt.year

        df_temp['Month_Display'] = df_temp[date_col].dt.strftime('%b %Y')

       

        time_agg = df_temp.groupby(['Year_Sort', 'FY_Sort', 'Month_Display'])[qty_col].sum().reset_index()

        time_agg = time_agg.sort_values(['Year_Sort', 'FY_Sort'])

       

        fig_time = px.bar(time_agg, x='Month_Display', y=qty_col, text_auto=',.0f',

                         color=qty_col, color_continuous_scale='Blues')

        fig_time.update_xaxes(categoryorder='array', categoryarray=time_agg['Month_Display'])

        st.plotly_chart(fig_time, use_container_width=True)



    # 6. RAW DATA

    with st.expander("🔍 View Filtered Raw Data"):

        st.dataframe(filtered_df, use_container_width=True, hide_index=True)



else:


    st.error("No data available. Check Google Sheet IDs.")
