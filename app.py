import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os
from PIL import Image
import io
import zipfile
import uuid

# -------------------------------

st.set_page_config(
    page_title="South Australia Disease Surveillance",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create directories if they don't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Load custom CSS
def load_css():
    if os.path.exists("styles.css"):
        with open("styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

def get_local_data_path():
    """Get the path to the local data file with proper handling for cloud deployments"""
    return os.path.join("data", "local_disease_data.csv")

def save_local_data(df):
    """Save local data with error handling"""
    try:
        local_path = get_local_data_path()
        df.to_csv(local_path, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

def load_local_data():
    """Load local data with error handling"""
    local_path = get_local_data_path()
    if os.path.exists(local_path):
        try:
            df = pd.read_csv(local_path)
            return df
        except Exception as e:
            st.error(f"Error loading local data: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# Load remote data with caching
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_remote_data():
    csv_url = "https://raw.githubusercontent.com/pullanagari/Disease_app/main/data_temp.csv"
    try:
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        st.error(f"Error loading remote data: {e}")
        return pd.DataFrame()

# Load all data (remote + local)
def load_all_data():
    df_remote = load_remote_data()
    df_local = load_local_data()
    
    if not df_local.empty and not df_remote.empty:
        df_combined = pd.concat([df_remote, df_local], ignore_index=True)
    elif not df_local.empty:
        df_combined = df_local.copy()
    elif not df_remote.empty:
        df_combined = df_remote.copy()
    else:
        df_combined = pd.DataFrame()

    if not df_combined.empty:
        # Normalize column names (optional)
        # Ensure date column is datetime
        if "date" in df_combined.columns:
            df_combined["date"] = pd.to_datetime(df_combined["date"], errors="coerce", dayfirst=True)
        # Ensure severity columns are numeric
        for col in ["severity1_percent", "severity2_percent", "severity3_percent"]:
            if col in df_combined.columns:
                df_combined[col] = pd.to_numeric(df_combined[col], errors="coerce")
        # Latitude/Longitude numeric
        for col in ["latitude", "longitude"]:
            if col in df_combined.columns:
                df_combined[col] = pd.to_numeric(df_combined[col], errors="coerce")
    
    return df_combined

# Initialize session state
if "df" not in st.session_state:
    st.session_state.df = load_all_data()

def reload_data():
    # Clear cache and reload all data
    try:
        st.cache_data.clear()
    except Exception:
        # in some streamlit versions clear might throw, ignore safely
        pass
    st.session_state.df = load_all_data()
    st.success("Data reloaded!")

# Sidebar CSS tweaks
sidebar_mobile_friendly = """
<style>
/* Prevent sidebar from collapsing but don't fix it */
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}

/* Optional: control sidebar width */
[data-testid="stSidebar"] {
    min-width: 250px !important;
    max-width: 300px !important;
}
</style>
"""
hide_menu_style = """
    <style>
        #MainMenu {visibility: hidden;}
    </style>
"""
st.markdown(hide_menu_style, unsafe_allow_html=True)
st.markdown(sidebar_mobile_friendly, unsafe_allow_html=True)

st.sidebar.markdown("## 🌾 South Australia Disease Surveillance")
menu = st.sidebar.radio("Navigation", ["Disease tracker", "Tag a disease", "About", "Resources"])

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    reload_data()

# Ensure df exists
df = st.session_state.get("df", pd.DataFrame())

# -------------------------------
# Disease Tracker Page
if menu == "Disease tracker":
    st.markdown("## 🗺 Disease Tracker")

    # Check if we have data
    if df.empty:
        st.warning("No data available. Please check your data sources.")
        st.stop()
    
    # Ensure we have the required columns
    required_columns = ["date", "crop", "disease1", "severity1_percent", "latitude", "longitude", "survey_location"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing required columns in data: {missing_columns}")
        st.stop()

    col1, col2, col3 = st.columns([1.5, 1, 1])
    with col1:
        crop = st.selectbox("Choose a Crop", ["All"] + sorted(df["crop"].dropna().unique()))
    with col2:
        disease = st.selectbox("Choose a Disease", ["All"] + sorted(df["disease1"].dropna().unique()))
    with col3:
        min_date = df["date"].min().date() if not df["date"].isna().all() else datetime(2020, 1, 1).date()
        max_date = df["date"].max().date() if not df["date"].isna().all() else datetime.today().date()
        date_range = st.date_input("Select Date Range", [min_date, max_date])

    # Filter data
    start_dt = pd.to_datetime(date_range[0])
    end_dt = pd.to_datetime(date_range[1])
    mask = (df["date"] >= start_dt) & (df["date"] <= end_dt)
    if crop != "All":
        mask &= df["crop"] == crop
    if disease != "All":
        mask &= df["disease1"] == disease

    df_filtered = df.loc[mask].copy()

    # Metrics
    st.markdown("### Key Metrics")
    if not df_filtered.empty:
        col1, col2, col3 = st.columns(3)
        total_surveys = len(df_filtered)
        max_sev = int(df_filtered["severity1_percent"].max()) if df_filtered["severity1_percent"].notna().any() else 0
        avg_sev = round(float(df_filtered["severity1_percent"].mean()) if df_filtered["severity1_percent"].notna().any() else 0.0, 1)
        col1.metric("Total Surveys", total_surveys)
        col2.metric("Max Severity (%)", max_sev)
        col3.metric("Average Severity (%)", avg_sev)
    else:
        st.warning("No data found for the selected filters.")

    # Create tabs for Map and Graph
    tab1, tab2 = st.tabs(["🗺️ Map", "📊 Graph"])
    with tab1:
        st.markdown("### Map View")
    
        unique_diseases = df["disease1"].dropna().unique()
        # Get a color list - use Plotly qualitative palette; if more diseases than palette, colors will recycle
        disease_colors = px.colors.qualitative.Set3
        disease_color_map = {d: disease_colors[i % len(disease_colors)] for i, d in enumerate(unique_diseases)}
    
        # Create the map
        default_location = [-36.76, 142.21]
        m = folium.Map(location=default_location, zoom_start=6)
    
        # Add markers
        for _, row in df_filtered.iterrows():
            lat = row.get("latitude")
            lon = row.get("longitude")
            if pd.notna(lat) and pd.notna(lon):
                popup_text = f"{row.get('survey_location', 'Unknown')}"
                if pd.notna(row.get("disease1")):
                    if pd.notna(row.get("severity1_percent")):
                        popup_text += f" | Disease1: {row['disease1']} ({row['severity1_percent']}%)"
                    else:
                        popup_text += f" | Disease1: {row['disease1']}"
                # Optional disease2/disease3 display
                for i in [2, 3]:
                    dcol = f"disease{i}"
                    scol = f"severity{i}_percent"
                    if dcol in row and pd.notna(row.get(dcol)) and str(row.get(dcol)).strip() not in ["", "None"]:
                        if pd.notna(row.get(scol)):
                            popup_text += f" | {dcol.capitalize()}: {row[dcol]} ({row[scol]}%)"
                        else:
                            popup_text += f" | {dcol.capitalize()}: {row[dcol]}"
    
                color = disease_color_map.get(row["disease1"], "gray")
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color=color,
                    fill=True,
                    fill_color=color,
                    popup=popup_text,
                ).add_to(m)
    
        # Render the map
        st_folium(m, width=800, height=450)

    with tab2:
        st.markdown("### Disease Severity Graph")
        
        # X-axis selection
        x_axis = st.selectbox("X-Axis", ["Crop", "Location", "Disease"])
        
        if not df_filtered.empty:
            # Determine x-axis column based on selection
            if x_axis == "Crop":
                x_col = "crop"
                title = f"Disease Severity by Crop"
            elif x_axis == "Location":
                x_col = "survey_location"
                title = f"Disease Severity by Location"
            else:  # Disease
                x_col = "disease1"
                title = f"Disease Severity by Disease Type"
            
            # Ensure the x_col exists
            if x_col not in df_filtered.columns:
                st.error(f"Column for x-axis not found: {x_col}")
            else:
                fig = px.bar(
                    df_filtered,
                    x=x_col,
                    y="severity1_percent",
                    title=title,
                    labels={"severity1_percent": "Severity (%)", x_col: x_axis},
                    color="disease1" if "disease1" in df_filtered.columns else None,
                    color_discrete_map=disease_color_map if "disease1" in df_filtered.columns else None,
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for the graph.")

    st.markdown("### Surveillance Summary")
    if not df_filtered.empty:
        # Option to show all columns or just selected ones
        show_all_columns = st.checkbox("Show all columns", value=False)
        
        if show_all_columns:
            st.dataframe(df_filtered)
        else:
            subset_cols = [c for c in ["date", "crop", "disease1", "survey_location", "severity1_percent"] if c in df_filtered.columns]
            st.dataframe(df_filtered[subset_cols])
        
        st.download_button(
            "Download CSV",
            df_filtered.to_csv(index=False).encode("utf-8"),
            file_name="survey.csv",
            mime="text/csv",
        )
    else:
        st.info("No data available for the selected filters.")

    st.markdown("### 📸 Download Photos")
    
    # Filter only rows with photos
    if "photo_filename" in df_filtered.columns:
        df_photos = df_filtered[df_filtered["photo_filename"].notna() & (df_filtered["photo_filename"] != "")]
    else:
        df_photos = pd.DataFrame()

    if not df_photos.empty:
        # Download all photos as ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for _, row in df_photos.iterrows():
                photo_path = os.path.join("uploads", row["photo_filename"])
                if os.path.exists(photo_path):
                    zf.write(photo_path, arcname=row["photo_filename"])
        st.download_button(
            "Download All Photos (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="disease_photos.zip",
            mime="application/zip",
        )
    else:
        st.info("No photos available for the selected filters.")

# -------------------------------
# Tag a Disease Page
elif menu == "Tag a disease":
    st.markdown("## 📌 Tag a Disease")

    # Centralized disease list to avoid typos / missing commas
    disease_list = [
        "None", "Stripe rust", "Leaf rust", "Stem rust", "Septoria tritici blotch", "Yellow leaf spot",
        "Powdery mildew", "Eye spot", "Black point", "Smut", "Spot form net blotch", "Net form net blotch",
        "Scald", "Red Leather Leaf", "Septoria avenae blotch", "Bacterial blight", "Ascochyta Blight",
        "Botrytis Grey Mold", "Sclerotinia white mould", "Chocolate Spot", "Cercospora leaf spot",
        "Downy mildew", "Black Spot", "Root Disease", "Virus", "Blackleg", "Other"
    ]

    with st.form("disease_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date", datetime.today())
            collector = st.selectbox(
                "Collector Name",
                ["Hari Dadu", "Rohan Kimber", "Tara Garrard", "Moshen Khani", "Kul Adhikari",
                 "Mark Butt", "Marzena Krysinka-Kaczmarek", "Michelle Russ", "Entesar Abood",
                 "Milica Grcic", "Nicole Thompson", "Blake Gontar", "Other"]
            )
            crop = st.selectbox(
                "Crop", ["Wheat", "Barley", "Canola", "Lentil", "Oats", "Faba beans",
                         "Vetch", "Field peas", "Chickpea", "Other"]
            )
            variety = st.text_input("Variety", "")
            plant_stage = st.selectbox(
                "Plant Growth Stage",
                ["Emergence", "Tillering", "Stem elongation", "Flowering", "Grain filling", "Maturity"],
            )
        with col2:
            disease1 = st.selectbox("Disease 1", disease_list[1:])  # require a real disease by default
            disease2 = st.selectbox("Disease 2", disease_list)
            disease3 = st.selectbox("Disease 3", disease_list)
            
            severity1 = st.slider("Severity 1 (%)", 0, 100, 0)
            severity2 = st.slider("Severity 2 (%)", 0, 100, 0)
            severity3 = st.slider("Severity 3 (%)", 0, 100, 0)
            latitude = st.text_input("Latitude", "-36.76")
            longitude = st.text_input("Longitude", "142.21")

        location = st.text_input("Location (Suburb)", "")
        field_type = st.text_input("Field Type", "")
        agronomist = st.text_input("Agronomist", "")
        field_notes = st.text_area("Field Notes (Optional)")
        sample_taken = st.selectbox("Sample Taken", ["Yes", "No", "N/A"])
        molecular_diagnosis = st.multiselect(
            "Action",
            ["Molecular diagnosis", "Mail a sample to collaborators", "Report back to farmers", "Single Spore isolation"]
        )

        uploaded_file = st.file_uploader("Attach Photo (Optional)", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("Submit")

        if submitted:
            if not all([crop, disease1, location]):
                st.error("Please fill in all required fields: Crop, Disease 1, and Location")
            else:
                # Generate a unique ID
                unique_id = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID
                
                photo_filename = ""
                if uploaded_file is not None:
                    ext = uploaded_file.name.split(".")[-1]
                    photo_filename = f"disease_photo_{unique_id}.{ext}"
                    save_path = os.path.join("uploads", photo_filename)
                    try:
                        with open(save_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                    except Exception as e:
                        st.error(f"Failed to save uploaded photo: {e}")
                        photo_filename = ""
                
                # Normalize "None" choices
                if disease2 == "None":
                    disease2 = ""
                    severity2 = 0
                if disease3 == "None":
                    disease3 = ""
                    severity3 = 0

                # Safe lat/lon conversion with defaults
                try:
                    lat_val = float(latitude) if str(latitude).strip() != "" else -36.76
                except Exception:
                    lat_val = -36.76
                try:
                    lon_val = float(longitude) if str(longitude).strip() != "" else 142.21
                except Exception:
                    lon_val = 142.21

                new_record = {
                    "id": unique_id,
                    "date": date.strftime("%d/%m/%Y"),
                    "collector_name": collector,
                    "field_type": field_type,
                    "Agronomist": agronomist,
                    "crop": crop,
                    "variety": variety,
                    "plant_stage": plant_stage,
                    "disease1": disease1,
                    "disease2": disease2,
                    "disease3": disease3,
                    "severity1_percent": int(severity1),
                    "severity2_percent": int(severity2),
                    "severity3_percent": int(severity3),
                    "latitude": lat_val,
                    "longitude": lon_val,
                    "survey_location": location,
                    "photo_filename": photo_filename if photo_filename else "",
                    "field_notes": field_notes,
                    "sample_taken": sample_taken,
                    "molecular_diagnosis": ", ".join(molecular_diagnosis) if molecular_diagnosis else "",
                }

                # Load existing local data
                local_data = load_local_data()
                if local_data.empty:
                    updated_data = pd.DataFrame([new_record])
                else:
                    updated_data = pd.concat([local_data, pd.DataFrame([new_record])], ignore_index=True)

                if save_local_data(updated_data):
                    st.success("✅ Submission successful! Data saved locally.")
                    # Force a refresh of the data by updating session state and rerunning
                    st.session_state.df = updated_data
                    reload_data()
                    if photo_filename:
                        # open saved path to display
                        try:
                            st.image(Image.open(os.path.join("uploads", photo_filename)), caption="Disease Photo", use_column_width=True)
                        except Exception as e:
                            st.warning(f"Saved photo could not be opened for display: {e}")
                    
                    st.rerun()
                else:
                    st.error("Failed to save data. Please try again.")

# -------------------------------
# About & Resources Page
elif menu == "About":
    st.markdown("## ℹ️ About SA Ds App")
    st.markdown(
        """
    This application supports field crop pathology staff during surveillance activities to upload disease information 
    and visualize disease severity through maps, graphs, and tables.

    **New Features:**
    - Photo attachment capability for disease documentation  
    - Local CSV data storage and export functionality  
    - Improved data management  

    **Tips:** - Use the 'Refresh Data' button in the sidebar to see newly submitted entries  
    - If data doesn't update automatically, try refreshing the page
    
    **Data Persistence:**
    - Your submitted data is now saved to a local file that persists across sessions
    - You can download your data using the export feature on the "Tag a disease" page
    """
    )

elif menu == "Resources":
    st.title("📚 Resources")
    st.markdown(
        """
        - [UteGuide: Disease Identification](https://uteguides.net.au/UteGuides/Details/8b4db434-297c-42d3-8ebe-e6b6520ea4e2)  
        - [NVT Disease ratings](https://nvt.grdc.com.au/nvt-disease-ratings)
        - [SARDI Molecular diagnostics](https://pir.sa.gov.au/sardi/services/molecular_diagnostics)
        - [SARDI Biosecurity](https://pir.sa.gov.au/sardi/crop_sciences/plant_health_and_biosecurity)
        """
    )
