import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os
from PIL import Image
import json
import requests
import io
import zipfile
import uuid  # Add this import for generating unique IDs

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
            return pd.read_csv(local_path)
        except Exception as e:
            st.error(f"Error loading local data: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# Load remote data with caching
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_remote_data():
    csv_url = "https://raw.githubusercontent.com/pullanagari/Disease_app/main/data_temp.csv"
    try:
        return pd.read_csv(csv_url)
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
        df_combined = df_local
    elif not df_remote.empty:
        df_combined = df_remote
    else:
        df_combined = pd.DataFrame()

    if not df_combined.empty and "date" in df_combined.columns:
        df_combined["date"] = pd.to_datetime(df_combined["date"], errors="coerce", dayfirst=True)
    
    return df_combined

# Initialize session state
if "df" not in st.session_state:
    st.session_state.df = load_all_data()

def reload_data():
    # Clear cache and reload all data
    st.cache_data.clear()
    st.session_state.df = load_all_data()
    st.success("Data reloaded!")

# ... (rest of your CSS and sidebar code remains the same)

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
menu = st.sidebar.radio("Navigation", ["Disease tracker", "Tag a disease", "About","Resources"])

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    reload_data()

# Make sure df exists in session state
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
df = st.session_state.df

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

    # ... (rest of your Disease Tracker code remains the same)

# -------------------------------
# Tag a Disease Page
elif menu == "Tag a disease":
    st.markdown("## 📌 Tag a Disease")

    with st.form("disease_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date", datetime.today())
            collector = st.selectbox(
                "Collector Name",
                ["Hari Dadu", "Rohan Kimber", "Tara Garrard","Moshen Khani", "Kul Adhikari", 
                 "Mark Butt","Marzena Krysinka-Kaczmarek","Michelle Russ","Entesar Abood", 
                 "Milica Grcic", "Nicole Thompson","Blake Gontar", "Other"]
            )
            crop = st.selectbox(
                "Crop", ["Wheat", "Barley", "Canola", "Lentil", "Oats","Faba beans",
                         "Vetch","Field peas","Chcickpea", "Other"]
            )
            variety = st.text_input("Variety", "")
            plant_stage = st.selectbox(
            "Plant Growth Stage",
            ["Emergence", "Tillering", "Stem elongation", "Flowering", "Grain filling", "Maturity"],
            )
        with col2:
            disease1 = st.selectbox("Disease 1", ["Stripe rust", "Leaf rust", "Stem rust", "Septoria tritici blotch", "Yellow leaf spot", "Powdery mildew", 
                                                  "Eye spot", "Black point", "Smut", "Spot form net blotch", "Net form net blotch", "Scald", "Red Leather Leaf",
                                                  "Septoria avenae blotch", "Bacterial blight", "Ascochyta Blight", "Botrytis Grey Mold", "Sclerotinia white mould", 
                                                  "Chocolate Spot","Cercospora leaf spot", "Downy mildew","Black Spot", "Root Disease" "Virus", "Blackleg", "Other"])
            disease2 = st.selectbox("Disease 2", ["None"] + ["Stripe rust", "Leaf rust", "Stem rust", "Septoria tritici blotch", "Yellow leaf spot", "Powdery mildew", 
                                                  "Eye spot", "Black point", "Smut", "Spot form net blotch", "Net form net blotch", "Scald", "Red Leather Leaf",
                                                  "Septoria avenae blotch", "Bacterial blight", "Ascochyta Blight", "Botrytis Grey Mold", "Sclerotinia white mould", 
                                                  "Chocolate Spot","Cercospora leaf spot", "Downy mildew","Black Spot", "Root Disease" "Virus", "Blackleg", "Other"])
            disease3 = st.selectbox("Disease 3", ["None"] + ["Stripe rust", "Leaf rust", "Stem rust", "Septoria tritici blotch", "Yellow leaf spot", "Powdery mildew", 
                                                  "Eye spot", "Black point", "Smut", "Spot form net blotch", "Net form net blotch", "Scald", "Red Leather Leaf",
                                                  "Septoria avenae blotch", "Bacterial blight", "Ascochyta Blight", "Botrytis Grey Mold", "Sclerotinia white mould", 
                                                  "Chocolate Spot","Cercospora leaf spot", "Downy mildew","Black Spot", "Root Disease" "Virus", "Blackleg", "Other"])
            
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
                
                photo_filename = None
                if uploaded_file is not None:
                    ext = uploaded_file.name.split(".")[-1]
                    photo_filename = f"disease_photo_{unique_id}.{ext}"
                    with open(os.path.join("uploads", photo_filename), "wb") as f:
                        f.write(uploaded_file.getbuffer())

                if disease2 == "None": disease2, severity2 = "", 0
                if disease3 == "None": disease3, severity3 = "", 0

                new_record = {
                    "id": unique_id,  # Add unique ID
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
                    "severity1_percent": severity1,
                    "severity2_percent": severity2,
                    "severity3_percent": severity3,
                    "latitude": float(latitude) if latitude else -36.76,
                    "longitude": float(longitude) if longitude else 142.21,
                    "survey_location": location,
                    "photo_filename": photo_filename if photo_filename else "",
                    "field_notes": field_notes,
                    "sample_taken": sample_taken,
                    "molecular_diagnosis": ", ".join(molecular_diagnosis) if molecular_diagnosis else "",
                }

                # Load existing local data
                local_data = load_local_data()
                updated_data = pd.concat([local_data, pd.DataFrame([new_record])], ignore_index=True) if not local_data.empty else pd.DataFrame([new_record])

                if save_local_data(updated_data):
                    st.success("✅ Submission successful! Data saved locally.")
                    # Force a refresh of the data
                    reload_data()
                    if uploaded_file:
                        st.image(Image.open(uploaded_file), caption="Disease Photo", use_column_width=True)
                    
                    # Automatically switch to Disease Tracker tab to see the updated data
                    st.session_state.menu = "Disease tracker"
                    st.experimental_rerun()
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

    **Tips:**  
    - Use the 'Refresh Data' button in the sidebar to see newly submitted entries  
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









