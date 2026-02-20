import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import re

# --- 1. APP CONFIGURATION ---
st.set_page_config(
    page_title="Keros Photogrammetry Hub", 
    page_icon="keros_proj_icon.png",  # Link to your PNG here
    layout="wide"
)
# --- 2. PASSWORD PROTECTION ---
def check_password():
    if "password" not in st.secrets:
        st.error("🔒 Password not configured in secrets.")
        return False
    if "password_correct" not in st.session_state:
        st.text_input("Project Password", type="password", 
                      on_change=lambda: st.session_state.update(password_correct=st.session_state.password == st.secrets["password"]), 
                      key="password")
        return False
    return st.session_state["password_correct"]

if not check_password():
    st.stop()

# --- 3. NAVIGATION ---
st.sidebar.image("kerosproj_icon.png", width=100) # Replace logo.png with your filename
st.sidebar.title("Navigation")
app_mode = st.sidebar.selectbox("Select Mode", [
    "Current 2026 Register", 
    "Legacy 2016-18 Archive",
    "Project Analytics"
])

# --- 3.5 MAIN PAGE HEADER ---
# This puts the large header image at the very top of the main content area
try:
    st.image("kerosimag.jpg", use_container_width=True, height=100) # Header spans the full width
except:
    st.title("The Keros Photogrammetry Project")

# --- 4. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
MAIN_URL = "https://docs.google.com/spreadsheets/d/1U1Nxu6X0NvVAWuHchChSSTzD_rAGNHgdtisP3_3OfbQ"
LEGACY_URL = "https://docs.google.com/spreadsheets/d/1r-4qViz9ojWm_2t9gJ0JqkOmv2gDSmHs7XXTGVvvXbU"

# Helper for Natural Sort
def natural_sort_df(df):
    df['Trench'] = df['Trench'].astype(str)
    df['t_sort'] = pd.to_numeric(df['Trench'].str.extract('(\d+)', expand=False), errors='coerce').fillna(0)
    sorted_df = df.sort_values(by=['Area', 't_sort', 'Name']).drop(columns=['t_sort'])
    return sorted_df

# ---------------------------------------------------------
# MODE: CURRENT 2026 REGISTER
# ---------------------------------------------------------
if app_mode == "Current 2026 Register":
    st.title("Keros Photogrammetry Register 2025-")
    df = conn.read(spreadsheet=MAIN_URL, ttl=600)
    df = natural_sort_df(df)

    checkbox_cols = ["Complete", "Model Cropped", "GIS uploaded"]
    for col in checkbox_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    
    st.header("1. Register New Layer")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1: date = st.date_input("Date", datetime.date.today())
        with c2: area = st.selectbox("Area", ["Dhaskalio", "Kavos", "Polygon2", "SDS", "Konakia"])
        with c3: trench = st.text_input("Trench")
        with c4: layer_name = st.text_input("Layer Name")
        notes = st.text_area("Initial Field Notes")
        if st.form_submit_button("Add to Register"):
            if trench and layer_name:
                new_row = pd.DataFrame([{"Date": date.strftime("%d.%m.%Y"), "Area": area, "Trench": trench, "Name": layer_name, "Complete": False, "Notes": notes}])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(spreadsheet=MAIN_URL, data=updated_df)
                st.success("Added!"); st.rerun()

    st.header("2. Processing Status")
    areas = ["All Areas"] + sorted(df['Area'].unique().tolist())
    tabs = st.tabs(areas)
    all_edits = []
    
    for i, a_name in enumerate(areas):
        with tabs[i]:
            view_df = df if a_name == "All Areas" else df[df['Area'] == a_name]
            edited = st.data_editor(view_df, key=f"ed_{a_name}", hide_index=True, use_container_width=True, height=600)
            all_edits.append(edited)

    if st.button("💾 Save All Changes"):
        final_df = df.copy()
        for ed in all_edits: 
            if ed is not None: final_df.update(ed)
        conn.update(spreadsheet=MAIN_URL, data=final_df)
        st.success("Updated!"); st.rerun()

# ---------------------------------------------------------
# MODE: LEGACY 2016-18 ARCHIVE
# ---------------------------------------------------------
elif app_mode == "Legacy 2016-18 Archive":
    st.title("🏛️ Legacy Archive (2016-2018)")
    ldf = conn.read(spreadsheet=LEGACY_URL, ttl=3600)
    if 'Year' in ldf.columns:
        ldf['Year'] = pd.to_numeric(ldf['Year'], errors='coerce').fillna(0).astype(int)
    ldf = natural_sort_df(ldf)

    st.header("🔍 Filter Archive")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        leg_years = ["All"] + sorted([y for y in ldf['Year'].unique() if y > 0])
        sel_year = st.selectbox("Filter by Year:", leg_years)
    with c2:
        leg_areas = ["All"] + sorted(ldf['Area'].astype(str).unique().tolist())
        sel_area = st.selectbox("Filter by Area:", leg_areas)
    with c3:
        leg_search = st.text_input("🔍 Search Layer Name", "")

    f_ldf = ldf.copy()
    if sel_year != "All": f_ldf = f_ldf[f_ldf['Year'] == sel_year]
    if sel_area != "All": f_ldf = f_ldf[f_ldf['Area'] == sel_area]
    if leg_search: f_ldf = f_ldf[f_ldf['Name'].str.contains(leg_search, case=False, na=False)]

    l_areas = ["All Areas"] + sorted(f_ldf['Area'].unique().tolist())
    l_tabs = st.tabs(l_areas)
    legacy_edits = []
    for i, a_name in enumerate(l_areas):
        with l_tabs[i]:
            tab_df = f_ldf if a_name == "All Areas" else f_ldf[f_ldf['Area'] == a_name]
            edited_leg = st.data_editor(tab_df, key=f"leg_ed_{a_name}", hide_index=True, use_container_width=True, height=600)
            legacy_edits.append(edited_leg)

    if st.button("💾 Save Legacy Changes"):
        updated_ldf = ldf.copy()
        for ed in legacy_edits:
            if ed is not None: updated_ldf.update(ed)
        conn.update(spreadsheet=LEGACY_URL, data=updated_ldf)
        st.success("Legacy Archive updated!"); st.rerun()

# ---------------------------------------------------------
# MODE: PROJECT ANALYTICS
# ---------------------------------------------------------
else:
    st.title("Project Analytics & Statistics")
    
    # Load both datasets
    df_curr = conn.read(spreadsheet=MAIN_URL, ttl=600)
    df_leg = conn.read(spreadsheet=LEGACY_URL, ttl=3600)
    
    st.markdown("---")
    
    # 1. CURRENT SEASON SUMMARY (2025/2026)
    st.header("⚡ Current Season Progress (2025-2026)")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        curr_summary = df_curr.groupby(['Area', 'Trench']).agg(
            Total=('Name', 'count'),
            Processed=('Complete', 'sum'),
            GIS=('GIS uploaded', 'sum')
        ).reset_index()
        st.dataframe(curr_summary, column_config={"Processed": st.column_config.ProgressColumn(min_value=0, max_value=10)}, use_container_width=True)
    
    with col2:
        st.metric("Total Layers (2026)", len(df_curr))
        st.metric("Processed %", f"{(df_curr['Complete'].sum()/len(df_curr)*100).round(1)}%")

    st.markdown("---")

    # 2. LEGACY ARCHIVE SUMMARY (2016-18)
    
    st.header("⚡ Previous Season Progress (2016-2018)")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        curr_summary = df_leg.groupby(['Area', 'Trench']).agg(
            Total=('Name', 'count'),
            Processed=('Complete', 'sum'),
            GIS=('GIS uploaded', 'sum')
        ).reset_index()
        st.dataframe(curr_summary, column_config={"Processed": st.column_config.ProgressColumn(min_value=0, max_value=10)}, use_container_width=True)
    
    with col2:
        st.metric("Total Layers (2016-2018)", len(df_leg))
        st.metric("Processed %", f"{(df_leg['Complete'].sum()/len(df_leg)*100).round(1)}%")

    # 3. YEARLY VOLUME CHARTS
    st.header("📈 Models per Trench (Comparison)")
    
    # Prepare data for charts
    df_curr['Area_Trench'] = df_curr['Area'] + " | " + df_curr['Trench'].astype(str)
    df_leg['Area_Trench'] = df_leg['Area'].astype(str) + " | " + df_leg['Trench'].astype(str)
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("2025-26 Season")
        st.bar_chart(df_curr.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count'), x="Area_Trench", y="Count", color="Area")
    
    with c2:
        st.subheader("2016-18 Legacy")
        st.bar_chart(df_leg.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count'), x="Area_Trench", y="Count", color="Area")