import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# --- App Configuration ---
st.set_page_config(page_title="Keros Photogrammetry Register", page_icon="📸", layout="wide")

st.title("📸 Keros Photogrammetry Register")
st.markdown("---")

# --- Google Sheets Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)
URL = st.secrets["connections"]["gsheets"]["spreadsheet"]

# Load data - ttl=0 ensures we don't see "stale" data after an update
df = conn.read(spreadsheet=URL, ttl=0)
# 1. Convert specific columns to Boolean (True/False)
# This prevents the "FLOAT" compatibility error
checkbox_cols = ["Complete", "Model Cropped", "GIS uploaded"]
for col in checkbox_cols:
    # We convert to bool, and fill empty cells with False
    df[col] = df[col].fillna(False).astype(bool)

# 2. Ensure Trench and Name are treated as text
df['Trench'] = df['Trench'].astype(str)
df['Area'] = df['Area'].astype(str)
df['Name'] = df['Name'].astype(str)
df['PSX File'] = df['PSX File'].astype(str)

# Ensure all necessary columns exist
expected_cols = ["Date", "Trench", "Area", "Name", "Device", "Complete", "Model Cropped", "GIS uploaded", "Notes"]
for col in expected_cols:
    if col not in df.columns:
        df[col] = False if "Complete" in col or "uploaded" in col or "Cropped" in col else ""

# --- SECTION 1: ADD NEW LAYER ---
st.header("1. Register New Layer")
with st.form("entry_form", clear_on_submit=True):
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        date = st.date_input("Date", datetime.date.today())
    with col2:
        area = st.selectbox("Area", ["Dhaskalio", "Kavos", "Polygon2", "SDS", "Konakia"])
    with col3:
        trench = st.text_input("Trench")
    with col4:
        layer_name = st.text_input("Layer Name (e.g. 1b2a)")
    with col5:
        device = st.selectbox("Device Taken", ["iPad 1", "iPad 2", "iPad 3", "iPhone1", "iPhone 2"])
    
    notes = st.text_area("Initial Field Notes")
    submit = st.form_submit_button("Add Layer to Register")

    if submit:
        if trench and layer_name:
            new_row = pd.DataFrame([{
                "Date": date.strftime("%d.%m.%Y"),
                "Area": str(area),
                "Trench": str(trench),
                "Name": layer_name,
                "Device": device,
                "Complete": False,
                "Model Cropped": False,
                "GIS uploaded": False,
                "Notes": notes
            }])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(spreadsheet=URL, data=updated_df)
            st.success(f"Added {layer_name} to the register!")
            st.rerun()
        else:
            st.error("Please provide both a Trench ID and a Layer Name.")

st.markdown("---")

# --- SECTION 2: LIVE REGISTER ---
st.header("2. Processing Status & Master Register")

# --- Data Preparation & Filtering ---
df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
df['Year'] = df['Date'].dt.year.fillna("Unknown").astype(str)

# Search & Filter UI (Shared across all tabs)
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    unique_years = ["All"] + sorted(df['Year'].unique().tolist(), reverse=True)
    selected_year = st.selectbox("Filter by Year:", unique_years)
with c2:
    df['Initials'] = df['Initials'].fillna("").astype(str)
    unique_initials = ["All"] + sorted([i for i in df['Initials'].unique() if i])
    selected_initials = st.selectbox("Filter by Initials:", unique_initials)
with c3:
    search_query = st.text_input("🔍 Search by Layer Name/Notes", "")

# --- Filter Data Logic ---
filtered_df = df.copy()
if selected_year != "All":
    filtered_df = filtered_df[filtered_df['Year'] == selected_year]
if selected_initials != "All":
    filtered_df = filtered_df[filtered_df['Initials'] == selected_initials]
if search_query:
    filtered_df = filtered_df[filtered_df['Name'].str.contains(search_query, case=False, na=False) | 
                               filtered_df['Notes'].str.contains(search_query, case=False, na=False)]

# Create Area Tabs
areas = ["All Areas"] + sorted(df['Area'].unique().tolist())
tabs = st.tabs(areas)

for i, area in enumerate(areas):
    with tabs[i]:
        # Filter for this specific tab's area
        if area == "All Areas":
            tab_df = filtered_df.copy()
        else:
            tab_df = filtered_df[filtered_df['Area'] == area].copy()
        
        # UI Polish: Use an emoji prefix for the "Complete" column to "shade" it
        tab_df['Status'] = tab_df['Complete'].apply(lambda x: "✅ Done" if x else "⏳ Pending")
        
        st.info(f"✏️ Editing {area} Register. Click 'Save' at the bottom after changes.")
        
        # The Editor
        edited_tab_df = st.data_editor(
            tab_df.drop(columns=['Year']), # Hide the helper column
            column_config={
                "Date": st.column_config.DatetimeColumn("Date", format="DD.MM.YYYY"),
                "Status": st.column_config.TextColumn("Current Status", disabled=True), # Visual indicator
                "Complete": st.column_config.CheckboxColumn("Processed?"),
                "Notes": st.column_config.TextColumn("Notes", width="large"),
                "Device": st.column_config.SelectboxColumn("Device", options=["iPad 1", "iPad 2", "iPad 3", "iPhone 1", "Other"]),
            },
            num_rows="dynamic",
            width="stretch",
            height=500,
            hide_index=True,
            key=f"editor_{area}" # Unique key per tab
        )

# --- SAVE BUTTON (Outside the loop so it's always at the bottom) ---
if st.button("💾 Save All Changes to Master Sheet"):
    # Note: Logic here needs to handle that we've edited a subset of data
    # The safest way is to update the master 'df' with our 'edited_tab_df'
    # but since we have multiple tabs, we rely on the user editing the active tab.
    
    # In this multi-tab setup, we sync the specific edited data back to the master
    df.update(edited_tab_df)
    
    # Format back to string for GSheets
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d.%m.%Y')
    
    conn.update(spreadsheet=URL, data=df)
    st.success("Master Register synced to Google Sheets!")
    st.rerun()

st.markdown("---")

# --- SECTION 3: STATISTICS ---
st.header("3. Project Statistics")

if not df.empty:
    # Top Row: Main Metrics
    c1, c2, c3, c4 = st.columns(4)
    
    total_count = len(df)
    processed_count = df["Complete"].astype(bool).sum()
    gis_count = df["GIS uploaded"].astype(bool).sum()
    progress = (processed_count / total_count * 100) if total_count > 0 else 0

    c1.metric("Total Models Registered", total_count)
    c2.metric("Total Photogram Processed", processed_count)
    c3.metric("Total in GIS", gis_count)
    c4.metric("Overall Progress", f"{progress:.1f}%")

    st.markdown("---")
    
   # --- Bottom Row: Charts ---
    st.markdown("---")
    
    # 1. Models per Trench & Area (Grouped Chart)
    st.write("#### 🗺️ Models per Trench (Colored by Area)")
    if not df.empty:
        # Group by both Trench and Area to get the counts
        trench_area_counts = df.groupby(['Trench', 'Area']).size().reset_index(name='count')
        
        # This creates a grouped bar chart
        st.bar_chart(
            trench_area_counts, 
            x="Trench", 
            y="count", 
            color="Area", # This separates the bars by Area color!
            width="stretch"
        )

    col_stats1, col_stats2 = st.columns(2)

    with col_stats1:
        st.write("#### 📍 Total Models by Area")
        area_counts = df['Area'].value_counts().reset_index(name='Total')
        # A simple bar chart for Area totals
        st.bar_chart(area_counts, x="Area", y="Total", color="#29b5e8")

    with col_stats2:
        st.write("#### 👤 Processing Output by Staff")
        processed_df = df[df["Complete"] == True].copy()
        if not processed_df.empty:
            staff_output = processed_df['Initials'].value_counts().reset_index()
            staff_output.columns = ['Initials', 'Completed Layers']
            st.bar_chart(staff_output, x="Initials", y="Completed Layers", color="#FF4B4B")
        else:
            st.info("No layers marked as 'Complete' yet.")

else:
    st.write("No data available yet to show statistics.")