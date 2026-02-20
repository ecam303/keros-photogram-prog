import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Keros Photogrammetry", page_icon="📸", layout="wide")

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
st.sidebar.title("🧭 Navigation")
app_mode = st.sidebar.selectbox("Select Dataset", ["Current 2026 Register", "Legacy 2016-18 Archive"])

# --- 4. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
MAIN_URL = "https://docs.google.com/spreadsheets/d/1U1Nxu6X0NvVAWuHchChSSTzD_rAGNHgdtisP3_3OfbQ"
LEGACY_URL = "https://docs.google.com/spreadsheets/d/1r-4qViz9ojWm_2t9gJ0JqkOmv2gDSmHs7XXTGVvvXbU"

# ---------------------------------------------------------
# MODE: CURRENT 2026 REGISTER
# ---------------------------------------------------------
if app_mode == "Current 2026 Register":
    st.title("📸 Keros Photogrammetry Register 2026")
    df = conn.read(spreadsheet=MAIN_URL, ttl=600)

    # Clean Data
    checkbox_cols = ["Complete", "Model Cropped", "GIS uploaded"]
    for col in checkbox_cols:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    
    # Section 1: Data Entry
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

    # Section 2: Editor
    st.header("2. Processing Status")
    df['Date_Text'] = df['Date'].astype(str)
    areas = ["All Areas"] + sorted(df['Area'].unique().tolist())
    tabs = st.tabs(areas)
    all_edits = []
    
    for i, a_name in enumerate(areas):
        with tabs[i]:
            view_df = df if a_name == "All Areas" else df[df['Area'] == a_name]
            # Trench Filter
            t_list = ["All"] + sorted(view_df['Trench'].astype(str).unique().tolist())
            sel_t = st.selectbox(f"Trench in {a_name}", t_list, key=f"t_{a_name}")
            if sel_t != "All": view_df = view_df[view_df['Trench'].astype(str) == sel_t]
            
            edited = st.data_editor(view_df, key=f"ed_{a_name}", hide_index=True)
            all_edits.append(edited)

    if st.button("💾 Save All Changes"):
        final_df = df.copy()
        for ed in all_edits: final_df.update(ed)
        conn.update(spreadsheet=MAIN_URL, data=final_df)
        st.success("Updated!"); st.rerun()

    # Section 3: Stats
    st.header("3. Statistics")
    stats_df = df.copy()
    stats_df['Area_Trench'] = stats_df['Area'] + " | " + stats_df['Trench'].astype(str)
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.write("#### 📅 2025 Trench Counts")
        d25 = stats_df[stats_df['Date_Text'].str.contains("2025", na=False)]
        if not d25.empty: st.bar_chart(d25.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count'), x="Area_Trench", y="Count", color="Area")
    with r1c2:
        st.write("#### 📅 2026 Trench Counts")
        d26 = stats_df[stats_df['Date_Text'].str.contains("2026", na=False)]
        if not d26.empty: st.bar_chart(d26.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count'), x="Area_Trench", y="Count", color="Area")

# ---------------------------------------------------------
# MODE: LEGACY 2016-18 ARCHIVE
# ---------------------------------------------------------
else:
    st.title("🏛️ Legacy Archive (2016-2018)")
    ldf = conn.read(spreadsheet=LEGACY_URL, ttl=3600)
    ldf['Date_Text'] = ldf['Date'].astype(str)
    
    st.subheader("Historical Registry (Read-Only)")
    st.dataframe(ldf, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.header("📊 Legacy Statistics")
    l_stats = ldf.copy()
    l_stats['Area_Trench'] = l_stats['Area'].astype(str) + " | " + l_stats['Trench'].astype(str)
    
    cols = st.columns(3)
    for idx, yr in enumerate(["2016", "2017", "2018"]):
        with cols[idx]:
            st.write(f"#### {yr} Models")
            yr_df = l_stats[l_stats['Date_Text'].str.contains(yr, na=False)]
            if not yr_df.empty:
                st.bar_chart(yr_df.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count'), x="Area_Trench", y="Count", color="Area")