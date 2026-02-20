import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

st.sidebar.title("Navigation")
page = st.sidebar.radio("Select Era", ["Current 2026", "Legacy 2016-18"])

if page == "Legacy 2016-18":
    # Run the legacy logic here or keep using switch_page
    st.switch_page("pages/1_Legacy_Data_2016-2018.py")

# --- App Configuration ---
st.set_page_config(page_title="Keros Photogrammetry Register", page_icon="📸", layout="wide")

st.title("Keros Photogrammetry Register 2025-")
st.markdown("---")

# --- Google Sheets Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)
MAIN_URL = "https://docs.google.com/spreadsheets/d/1U1Nxu6X0NvVAWuHchChSSTzD_rAGNHgdtisP3_3OfbQ"

# Pass that URL into the read function
df = conn.read(spreadsheet=MAIN_URL, ttl=600)

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
st.title("📸 Keros Photogrammetry Register 2026")

# Navigation Button to Legacy
if st.button("🏛️ Go to 2016-2018 Archive"):
    st.switch_page("pages/1_Legacy_Data_2016-2018.py")

st.markdown("---")

# --- SECTION 1: ADD NEW LAYER ---
st.header("Register New Layer")
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
            conn.update(spreadsheet=MAIN_URL, data=updated_df)
            st.success(f"Added {layer_name} to the register!")
            st.rerun()
        else:
            st.error("Please provide both a Trench ID and a Layer Name.")

st.markdown("---")

# --- SECTION 2: LIVE REGISTER ---
st.header("Processing Status & Master Register")

# --- Data Preparation ---
df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
df['Year'] = df['Date'].dt.year.fillna("Unknown").astype(str)

# --- Top-Level Global Filters ---
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

# Apply Global Filters first
filtered_df = df.copy()
if selected_year != "All":
    filtered_df = filtered_df[filtered_df['Year'] == selected_year]
if selected_initials != "All":
    filtered_df = filtered_df[filtered_df['Initials'] == selected_initials]
if search_query:
    filtered_df = filtered_df[
        filtered_df['Name'].str.contains(search_query, case=False, na=False) | 
        filtered_df['Notes'].str.contains(search_query, case=False, na=False)
    ]

# --- Area Tabs ---
areas = ["All Areas"] + sorted(df['Area'].unique().tolist())
tabs = st.tabs(areas)

# We store the edited results here
all_edits = []

for i, area in enumerate(areas):
    with tabs[i]:
        # 1. Sub-filter for Area
        if area == "All Areas":
            area_df = filtered_df.copy()
        else:
            area_df = filtered_df[filtered_df['Area'] == area].copy()
        
        # 2. THE TRENCH QUERY (Specific to this Area)
        area_df['Trench'] = area_df['Trench'].astype(str)
        trench_list = ["All Trenches"] + sorted(area_df['Trench'].unique().tolist())
        selected_trench = st.selectbox(f"Select Trench in {area}:", trench_list, key=f"trench_sel_{area}")
        
        if selected_trench != "All Trenches":
            area_df = area_df[area_df['Trench'] == selected_trench]

        # 3. Add the visual Status emoji
        area_df['Model Status'] = area_df['Complete'].apply(lambda x: "✅ Done" if x else "⏳ Pending")
        
        # 4. The Editor
        edited_tab = st.data_editor(
            area_df.drop(columns=['Year']),
            column_config={
                "Date": st.column_config.DatetimeColumn("Date", format="DD.MM.YYYY"),
                "Model Status": st.column_config.TextColumn("Model Status", disabled=True),
                "Complete": st.column_config.CheckboxColumn("Processed?"),
                "Notes": st.column_config.TextColumn("Notes", width="large"),
                "Device": st.column_config.SelectboxColumn("Device", options=["iPad 1", "iPad 2", "iPad 3", "iPhone 1", "Other"]),
            },
            num_rows="dynamic",
            width="stretch",
            height=500,
            hide_index=True,
            key=f"editor_{area}"
        )
        all_edits.append(edited_tab)

# --- Save Button ---
st.markdown("---")
if st.button("💾 Save All Changes"):
    # Create a fresh copy of master df
    final_df = df.copy()
    
    # Update the master dataframe with changes from the editors
    for edited_data in all_edits:
        if edited_data is not None:
            # We match by the index to ensure the right rows are updated
            final_df.update(edited_data)
    
    # Final cleanup: Convert date back to string for GSheets
    final_df['Date'] = pd.to_datetime(final_df['Date']).dt.strftime('%d.%m.%Y')
    
    conn.update(spreadsheet=MAIN_URL, data=final_df)
    st.balloons()
    st.success("Google Sheet successfully updated!")
    st.rerun()

st.markdown("---")

# --- SECTION 3: STATISTICS ---
# --- SECTION 3: STATISTICS ---
st.header("3. Project Statistics")

if not df.empty:
    stats_df = df.copy()
    stats_df['Date_Text'] = stats_df['Date'].astype(str)
    
    # 1. Create a Sorting Label: "Area | Trench"
    # This ensures the X-axis follows Area order first
    stats_df['Area_Trench'] = stats_df['Area'] + " | " + stats_df['Trench'].astype(str)

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    total_count = len(df)
    processed_count = df["Complete"].astype(bool).sum()
    gis_count = df["GIS uploaded"].astype(bool).sum()
    progress = (processed_count / total_count * 100) if total_count > 0 else 0

    c1.metric("Total Models", total_count)
    c2.metric("Processed", processed_count)
    c3.metric("In GIS", gis_count)
    c4.metric("Progress", f"{progress:.1f}%")

    st.markdown("---")

    # ROW 1: YEARLY TRENCH BREAKDOWN
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        st.write("#### 📅 2025: Models per Trench (Sorted by Area)")
        df_2025 = stats_df[stats_df['Date_Text'].str.contains("2025", na=False)]
        if not df_2025.empty:
            # Group by our new label to keep bars separate but sorted
            t_2025 = df_2025.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count')
            t_2025 = t_2025.sort_values(['Area', 'Area_Trench'])
            st.bar_chart(t_2025, x="Area_Trench", y="Count", color="Area")
        else:
            st.info("No 2025 data.")

    with row1_col2:
        st.write("#### 📅 2026: Models per Trench (Sorted by Area)")
        df_2026 = stats_df[stats_df['Date_Text'].str.contains("2026", na=False)]
        if not df_2026.empty:
            t_2026 = df_2026.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count')
            t_2026 = t_2026.sort_values(['Area', 'Area_Trench'])
            st.bar_chart(t_2026, x="Area_Trench", y="Count", color="Area")
        else:
            st.info("No 2026 data.")

    st.markdown("---")

    # ROW 2: STAFF & AREA TOTALS
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.write("#### 👤 Total Layers by Initial")
        staff_counts = stats_df.groupby('Initials').size().reset_index(name='Total')
        st.bar_chart(staff_counts, x="Initials", y="Total", color="#FF4B4B")

    with row2_col2:
        st.write("#### 🗺️ Total Layers by Area")
        area_total = stats_df.groupby('Area').size().reset_index(name='Total')
        st.bar_chart(area_total, x="Area", y="Total", color="Area")

else:
    st.info("No data available for statistics.")