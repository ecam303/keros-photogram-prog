import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# --- Page Configuration ---
st.set_page_config(page_title="Legacy Register (2016-18)", page_icon="🏛️", layout="wide")

st.title("🏛️ Legacy Photogrammetry Register (2016-2018)")

# Navigation Button back to Main
if st.button("⬅️ Back to Current 2026 Register"):
    st.switch_page("streamlit_app.py")

st.markdown("---")
st.info("This is a read-only archive of historical data. New entries should be made on the main page.")


# --- Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)
# REPLACE THIS URL with your 2018 spreadsheet link
LEGACY_URL = "https://docs.google.com/spreadsheets/d/1r-4qViz9ojWm_2t9gJ0JqkOmv2gDSmHs7XXTGVvvXbU"

# Load data
df = conn.read(spreadsheet=LEGACY_URL, ttl=3600) # Higher TTL since this data doesn't change

# --- Data Cleaning ---
df['Date_Text'] = df['Date'].astype(str)
if 'Area' not in df.columns: df['Area'] = "Unknown"
if 'Trench' not in df.columns: df['Trench'] = "Unknown"
df['Area_Trench'] = df['Area'] + " | " + df['Trench'].astype(str)

# --- Filters ---
st.header("🔍 Search Historical Records")
c1, c2 = st.columns([1, 2])
with c1:
    search_area = st.selectbox("Filter by Area", ["All Areas"] + sorted(df['Area'].unique().tolist()))
with c2:
    search_query = st.text_input("Search Layer Names or Notes", "")

# Apply Filters
display_df = df.copy()
if search_area != "All Areas":
    display_df = display_df[display_df['Area'] == search_area]
if search_query:
    display_df = display_df[display_df['Name'].str.contains(search_query, case=False, na=False)]

# --- Archive Table ---
# We use a static dataframe here because it's read-only
st.dataframe(
    display_df,
    column_config={
        "Notes": st.column_config.TextColumn("Notes", width="large"),
        "Complete": st.column_config.CheckboxColumn("Processed?"),
    },
    use_container_width=True, # 2026 update: width="stretch" also works here
    hide_index=True,
    height=500
)

# --- SECTION 3: LEGACY STATISTICS ---
st.markdown("---")
st.header("📊 2016-2018 Site Statistics")

row1_col1, row1_col2, row1_col3 = st.columns(3)
years = ["2016", "2017", "2018"]
cols = [row1_col1, row1_col2, row1_col3]

for yr, col in zip(years, cols):
    with col:
        st.write(f"#### 📅 {yr} Models")
        year_df = display_df[display_df['Date_Text'].str.contains(yr, na=False)]
        if not year_df.empty:
            t_counts = year_df.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count')
            st.bar_chart(t_counts.sort_values('Area'), x="Area_Trench", y="Count", color="Area")
        else:
            st.caption(f"No records found for {yr}")

st.write("#### 🗺️ Total Legacy Distribution by Area")
area_total = display_df.groupby('Area').size().reset_index(name='Total')
st.bar_chart(area_total, x="Area", y="Total", color="Area")