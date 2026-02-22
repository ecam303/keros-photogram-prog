import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import re
import base64
import time

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Keros Photogrammetry Hub", page_icon="icon.png", layout="wide")

# --- 2. CUSTOM CSS ---
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        .stTextInput { max-width: 400px; margin: 0 auto; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. HEADER HELPER & DISPLAY ---
def get_base64(bin_file):
    with open(bin_file, 'rb') as f:
        return base64.b64encode(f.read()).decode()

try:
    bin_str = get_base64('kerosimag.jpg')
    st.markdown(f"""
        <div style="
            background-image: linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.4)), url('data:image/jpg;base64,{bin_str}');
            background-size: cover; background-position: center 40%; height: 250px;
            display: flex; align-items: center; justify-content: center;
            border-radius: 15px; margin-bottom: 30px; border: 2px solid #ddd;
        ">
            <h1 style="color: white; text-shadow: 3px 3px 6px #000000; font-family: 'Helvetica Neue', Arial; font-size: 3rem; text-align: center;">
                The Keros Photogrammetry Project
            </h1>
        </div>
        """, unsafe_allow_html=True)
except:
    st.title("The Keros Photogrammetry Project")

# --- 4. PASSWORD PROTECTION ---
def check_password():
    if "password_correct" not in st.session_state:
        st.write("🔒 **Please enter the project password to access the registries.**")
        st.text_input("Project Password", type="password", 
                      on_change=lambda: st.session_state.update(password_correct=(st.session_state.password == st.secrets["password"])), 
                      key="password")
        return False
    return st.session_state["password_correct"]

if not check_password():
    st.stop()

# --- 5. NAVIGATION ---
try:
    st.sidebar.image("kerosproj_icon.png", width=80)
except:
    pass
st.sidebar.title("Navigation")
app_mode = st.sidebar.selectbox("Select Mode", [
    "📝 New Layer Entry",
    "🔄 Processing Status (2026)", 
    "🏛️ Legacy 2016-18 Archive",
    "📊 Project Analytics"
])

# --- 6. CONNECTIONS & HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)
MAIN_URL = "https://docs.google.com/spreadsheets/d/1U1Nxu6X0NvVAWuHchChSSTzD_rAGNHgdtisP3_3OfbQ"
LEGACY_URL = "https://docs.google.com/spreadsheets/d/1r-4qViz9ojWm_2t9gJ0JqkOmv2gDSmHs7XXTGVvvXbU"

def natural_sort_df(df):
    df['Trench'] = df['Trench'].astype(str)
    df['t_sort'] = pd.to_numeric(df['Trench'].str.extract('(\d+)', expand=False), errors='coerce').fillna(0)
    return df.sort_values(by=['Area', 't_sort', 'Name']).drop(columns=['t_sort'])

# ---------------------------------------------------------
# MODE: NEW LAYER ENTRY
# ---------------------------------------------------------
if app_mode == "📝 New Layer Entry":
    st.header("📝 Register New Photogrammetry Layer")
    df = conn.read(spreadsheet=MAIN_URL, ttl=0)
    
    with st.form("entry_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            date = st.date_input("Date of Capture", datetime.date.today())
            area = st.selectbox("Area", ["Dhaskalio", "Kavos", "Polygon2", "SDS", "Konakia"])
        with c2:
            trench = st.text_input("Trench ID (e.g., 12, 4A)")
            layer_name = st.text_input("Layer Name / ID")
        
        notes = st.text_area("Field Notes")
        
        if st.form_submit_button("➕ Submit to Register"):
            if trench and layer_name:
                new_row = pd.DataFrame([{"Date": date.strftime("%d.%m.%Y"), "Area": area, "Trench": trench, "Name": layer_name, "Complete": False, "GIS uploaded": False, "Notes": notes}])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(spreadsheet=MAIN_URL, data=updated_df)
                st.success(f"Successfully added Layer: {layer_name}")
                st.balloons()

# ---------------------------------------------------------
# MODE: PROCESSING STATUS (2026)
# ---------------------------------------------------------
elif app_mode == "🔄 Processing Status (2026)":
    st.header("🔄 Current Season Processing Status")
    
    # 1. READ (Cached)
    df = conn.read(spreadsheet=MAIN_URL, ttl=600)
    
    # 2. DATA TYPE FIX (Strictly for the checkboxes)
    for col in ["Complete", "GIS uploaded", "Model Cropped"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.upper().str.strip().isin(['1', '1.0', 'TRUE'])
    
    df = natural_sort_df(df)

    # 3. QUICK ADD (Immediate Sync - Use this for new rows!)
    with st.container(border=True):
        st.write("➕ **Quick Add New Layer** (Saves Immediately)")
        c1, c2, c3, c4 = st.columns([1.5, 1, 2, 1])
        with c1:
            q_area = st.selectbox("Area", ["Dhaskalio", "Kavos", "Polygon2", "SDS", "Konakia"], key="q_a")
        with c2:
            q_trench = st.text_input("Trench", key="q_t")
        with c3:
            q_name = st.text_input("Layer Name", key="q_n")
        with c4:
            st.write("##")
            if st.button("Add to Cloud", use_container_width=True):
                if q_trench and q_name:
                    new_row = pd.DataFrame([{
                        "Date": datetime.date.today().strftime("%d.%m.%Y"),
                        "Area": q_area, "Trench": q_trench, "Name": q_name,
                        "Complete": False, "GIS uploaded": False, "Model Cropped": False, "Notes": ""
                    }])
                    # PUSH IMMEDIATELY
                    conn.update(spreadsheet=MAIN_URL, data=pd.concat([df, new_row], ignore_index=True))
                    st.cache_data.clear()
                    st.rerun()

    st.write("---")

    # 4. TABS & EDITOR (Logic Protected)
    # Note: We REMOVED "All Areas" from the editor to prevent data deletion errors
    area_list = sorted(df['Area'].unique().tolist())
    tabs = st.tabs(area_list)
    
    # We use a dictionary to track changes per tab
    tab_changes = {}
    
    for i, a_name in enumerate(area_list):
        with tabs[i]:
            view_df = df[df['Area'] == a_name].copy()
            
            t_list = ["All"] + sorted(view_df['Trench'].unique().tolist(), 
                                      key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 0)
            sel_t = st.selectbox(f"Filter Trench", t_list, key=f"t_{a_name}")
            
            display_df = view_df if sel_t == "All" else view_df[view_df['Trench'] == sel_t]
            
            edited = st.data_editor(
                display_df, 
                key=f"ed_{a_name}_{sel_t}", 
                hide_index=True, 
                use_container_width=True,
                num_rows="fixed", # Disable the (+) button inside the table to prevent index errors
                column_config={
                    "Complete": st.column_config.CheckboxColumn(),
                    "GIS uploaded": st.column_config.CheckboxColumn(),
                    "Model Cropped": st.column_config.CheckboxColumn()
                }
            )
            tab_changes[f"{a_name}_{sel_t}"] = (edited, display_df)

# 5. THE GLOBAL SAVE (Cache-Safe Version)
    if st.button("💾 SAVE ALL EDITS", use_container_width=True):
        # Trigger an immediate cache clear so the app doesn't "remember" the old state
        st.cache_data.clear() 
        
        with st.status("Pushing edits to Cloud...") as status:
            new_df = df.copy()
            change_detected = False
            
            for key, (edited_data, original_display) in tab_changes.items():
                # Compare the current state of the editor to what was originally shown
                if not edited_data.equals(original_display):
                    change_detected = True
                    
                    # We use the index of the original_display to ensure we 
                    # update the EXACT rows in the master dataframe
                    for idx in edited_data.index:
                        new_df.loc[idx, ["Complete", "GIS uploaded", "Model Cropped", "Notes"]] = \
                            edited_data.loc[idx, ["Complete", "GIS uploaded", "Model Cropped", "Notes"]]

            if change_detected:
                try:
                    conn.update(spreadsheet=MAIN_URL, data=new_df)
                    status.update(label="✅ Cloud Sync Successful!", state="complete")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Save failed: {e}")
            else:
                st.info("No changes were detected in the tables.")

# ---------------------------------------------------------
# MODE: LEGACY 2016-18 ARCHIVE
# ---------------------------------------------------------
elif app_mode == "🏛️ Legacy 2016-18 Archive":
    st.header("🏛️ Legacy Archive (2016-2018)")
    ldf = conn.read(spreadsheet=LEGACY_URL, ttl=3600)
    ldf = natural_sort_df(ldf)
    
    for col in ["Complete", "GIS uploaded"]:
        if col in ldf.columns:
            ldf[col] = ldf[col].fillna(False).astype(bool)

    st.subheader("🔍 Global Filters")
    c1, c2 = st.columns(2)
    with c1:
        years = ["All"] + sorted([int(y) for y in ldf['Year'].unique() if pd.notnull(y)])
        sel_year = st.selectbox("Filter by Year", years)
    with c2:
        leg_search = st.text_input("🔍 Search Layer Name (Across all areas)")

    f_ldf = ldf.copy()
    if sel_year != "All": f_ldf = f_ldf[f_ldf['Year'] == sel_year]
    if leg_search: f_ldf = f_ldf[f_ldf['Name'].str.contains(leg_search, case=False, na=False)]

    l_areas = ["All Areas"] + sorted(f_ldf['Area'].unique().tolist())
    l_tabs = st.tabs(l_areas)
    legacy_edits = []

    for i, a_name in enumerate(l_areas):
        with l_tabs[i]:
            tab_df = f_ldf if a_name == "All Areas" else f_ldf[f_ldf['Area'] == a_name]
            lt_list = ["All"] + sorted(tab_df['Trench'].unique().tolist(),
                                      key=lambda x: int(re.search(r'\d+', str(x)).group()) if re.search(r'\d+', str(x)) else 0)
            sel_lt = st.selectbox(f"Filter Trench in {a_name}", lt_list, key=f"lt_sel_{a_name}")
            
            if sel_lt != "All":
                tab_df = tab_df[tab_df['Trench'] == sel_lt]

            edited_leg = st.data_editor(tab_df, key=f"leg_ed_{a_name}", hide_index=True, use_container_width=True, height=600)
            legacy_edits.append((edited_leg, tab_df))

    if st.button("💾 Save Archive Changes"):
        updated_ldf = ldf.copy()
        for ed_l, tab_view_l in legacy_edits:
            if ed_l is not None and "edited_rows" in ed_l:
                for idx, updates in ed_l["edited_rows"].items():
                    actual_idx = tab_view_l.index[idx]
                    for col, val in updates.items():
                        updated_ldf.at[actual_idx, col] = val
        conn.update(spreadsheet=LEGACY_URL, data=updated_ldf)
        st.success("Legacy Archive Updated!"); st.rerun()

# ---------------------------------------------------------
# MODE: PROJECT ANALYTICS
# ---------------------------------------------------------
else:
    st.header("📊 Project Statistics")
    df_curr = conn.read(spreadsheet=MAIN_URL, ttl=300)
    df_leg = conn.read(spreadsheet=LEGACY_URL, ttl=3600)

    def get_summary(df):
        summary = df.groupby(['Area', 'Trench']).agg(
            Total=('Name', 'count'),
            Processed=('Complete', 'sum'),
            GIS=('GIS uploaded', 'sum')
        ).reset_index()
        summary['% Complete'] = (summary['Processed'] / summary['Total'] * 100).round(1)
        return summary

    st.subheader("⚡ Current Season Progress (2025-26)")
    m1, m2, m3 = st.columns(3)
    total_curr = len(df_curr)
    done_curr = df_curr['Complete'].sum() if 'Complete' in df_curr.columns else 0
    perc_curr = (done_curr / total_curr * 100).round(1) if total_curr > 0 else 0
    m1.metric("Total Layers Registered", total_curr)
    m2.metric("Total Processed", int(done_curr))
    m3.metric("Overall Completion", f"{perc_curr}%")

    st.dataframe(get_summary(df_curr), column_config={
        "% Complete": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)
    }, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🏛️ Legacy Progress (2016-18)")
    l1, l2, l3 = st.columns(3)
    total_leg = len(df_leg)
    done_leg = df_leg['Complete'].sum() if 'Complete' in df_leg.columns else 0
    perc_leg = (done_leg / total_leg * 100).round(1) if total_leg > 0 else 0
    l1.metric("Total Archive Layers", total_leg)
    l2.metric("Total Processed", int(done_leg))
    l3.metric("Overall Completion", f"{perc_leg}%")

    st.dataframe(get_summary(df_leg), column_config={
        "% Complete": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)
    }, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📈 Excavation Volume per Trench")
    df_curr['Area_Trench'] = df_curr['Area'] + " | " + df_curr['Trench'].astype(str)
    df_leg['Area_Trench'] = df_leg['Area'].astype(str) + " | " + df_leg['Trench'].astype(str)
    
    c1, c2 = st.columns(2)
    with c1:
        st.write("**2025-26 Season**")
        st.bar_chart(df_curr.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count'), x="Area_Trench", y="Count", color="Area")
    with c2:
        st.write("**2016-18 Legacy**")
        st.bar_chart(df_leg.groupby(['Area_Trench', 'Area']).size().reset_index(name='Count'), x="Area_Trench", y="Count", color="Area")