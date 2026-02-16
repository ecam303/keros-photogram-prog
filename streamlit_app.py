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

# --- Data Preparation for Filtering ---
# Ensure Date is in a format pandas can read as a date
df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
# Create a 'Year' column for the filter (handle empty dates with "Unknown")
df['Year'] = df['Date'].dt.year.fillna("Unknown").astype(str)

# --- Search and Filter UI ---
c1, c2, c3, c4 = st.columns([1, 1, 1, 2]) # 4 columns now
with c1:
    unique_years = ["All"] + sorted(df['Year'].unique().tolist(), reverse=True)
    selected_year = st.selectbox("Filter by Year:", unique_years)

with c2:
    df['Trench'] = df['Trench'].astype(str)
    unique_trenches = ["All"] + sorted(df['Trench'].unique().tolist())
    selected_trench = st.selectbox("Filter by Trench:", unique_trenches)

with c3:
    df['Initials'] = df['Initials'].fillna("").astype(str)
    unique_initials = ["All"] + sorted([i for i in df['Initials'].unique() if i])
    selected_initials = st.selectbox("Filter by Initials:", unique_initials)

with c4:
    search_query = st.text_input("🔍 Search by Layer Name/Notes", "")

# --- Apply Filters ---
display_df = df.copy()

if selected_year != "All":
    display_df = display_df[display_df['Year'] == selected_year]

if selected_trench != "All":
    display_df = display_df[display_df['Trench'] == selected_trench]

if selected_initials != "All":
    display_df = display_df[display_df['Initials'] == selected_initials]

if search_query:
    display_df = display_df[
        display_df['Name'].str.contains(search_query, case=False, na=False) | 
        display_df['Notes'].str.contains(search_query, case=False, na=False)
    ]

# Remove the helper 'Year' column before showing the table (keeps it clean)
display_df = display_df.drop(columns=['Year'])

edited_df = st.data_editor(
    display_df,
    column_config={
        # 1. Matches the DATETIME type we created for the Year filter
        "Date": st.column_config.DatetimeColumn(
            "Date", 
            format="DD.MM.YYYY", 
            step=60
        ), 
        "Trench": st.column_config.TextColumn("Trench"),
        "Name": st.column_config.TextColumn("Layer Name"),
        "Device": st.column_config.SelectboxColumn(
            "Device", 
            options=["iPad 1", "iPad 2", "iPad 3", "iPhone1", "Other"]
        ),
        "Initials": st.column_config.TextColumn("Initials"),
        "Complete": st.column_config.CheckboxColumn("Processed?"),
        "Model Cropped?": st.column_config.CheckboxColumn("Cropped?"),
        "GIS uploaded?": st.column_config.CheckboxColumn("In GIS?"),
        "Notes": st.column_config.TextColumn("Notes", width="large"),
    },
    num_rows="dynamic",
    width="stretch",  # Updated for 2026 Streamlit standards
    hide_index=True,
)

if st.button("💾 Save All Changes"):
    # Merge edits back to the main dataframe
    df.update(edited_df)
    conn.update(spreadsheet=URL, data=df)
    st.success("Google Sheet synced!")

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
    
    # Bottom Row: Two Charts
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.write("#### Models per Trench")
        # Count total layers assigned to each trench
        trench_counts = df['Trench'].value_counts().reset_index(name='count')
        st.bar_chart(trench_counts, x="Trench", y="count", color="#29b5e8")

    with col_chart2:
        st.write("#### Processing Output by Staff")
        # Filter to only see completed work
        processed_df = df[df["Complete"] == True]
        
        if not processed_df.empty:
            # Count how many "Complete" rows belong to each person
            staff_output = processed_df['Initials'].value_counts().reset_index(name='Completed Layers')
            st.bar_chart(staff_output, x="Initials", y="Completed Layers", color="#FF4B4B")
        else:
            st.info("No layers marked as 'Complete' yet to show staff stats.")

else:
    st.write("No data available yet to show statistics.")