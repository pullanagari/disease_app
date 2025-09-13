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
import re
import requests

import base64
import requests

# -------------------------------
# GitHub helper functions
# -------------------------------
def github_api_request(method, url, data=None):
    token = st.secrets["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {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}"}
    r = requests.request(method, url, headers=headers, json=data)
    return r

def save_csv_to_github(df):
    try:
        token = st.secrets["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"]
        repo = st.secrets["pullanagari/Disease_app"]
        branch = st.secrets.get("main", "main")
    except KeyError as e:
        st.error(f"Missing secret: {e}. Please set it in Streamlit secrets.")
        return False
     # Prepare new content
    content = df.to_csv(index=False).encode("utf-8")
    b64_content = base64.b64encode(content).decode()

    data = {
        "message": "Update disease data via Streamlit app",
        "content": b64_content,
        "branch": branch,
    }
    if sha:
        data["sha"] = sha

    r = github_api_request("PUT", url, data)
    if r.status_code in [200, 201]:
        return True
    else:
        st.error(f"GitHub CSV save failed: {r.json()}")
        return False


def save_photo_to_github(file_bytes, filename, folder="photos", branch="main"):
    repo = st.secrets["GITHUB_REPO"]
    path = f"{folder}/{filename}"
    url = f"https://api.github.com/repos/{pullanagari/Disease_app}/contents/{data_temp.csv}"

    # Get file SHA if exists
    r = github_api_request("GET", url)
    sha = r.json().get("sha") if r.status_code == 200 else None

    # Encode file
    b64_content = base64.b64encode(file_bytes).decode()

    data = {
        "message": f"Upload photo {filename}",
        "content": b64_content,
        "branch": branch,
    }
    if sha:
        data["sha"] = sha

    r = github_api_request("PUT", url, data)
    if r.status_code in [200, 201]:
        # Return raw GitHub URL for future display
        return f"https://raw.githubusercontent.com/{pullanagari/Disease_app}/{branch}/{data_temp.csv}"
    else:
        st.error(f"GitHub photo upload failed: {r.json()}")
        return None


# -------------------------------
# Page config (must be before any Streamlit UI code)
st.set_page_config(
    page_title="South Australia Disease Surveillance",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# Setup
csv_url = "https://raw.githubusercontent.com/pullanagari/Disease_app/main/data_temp.csv"

# Create directories if they don't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Load custom CSS
def load_css():
    if os.path.exists("styles.css"):
        with open("styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Hide GitHub logo
hide_github_logo = """
<style>
.css-1v0mbdj {
    display: none !important;
}
</style>
"""
st.markdown(hide_github_logo, unsafe_allow_html=True)

# -------------------------------
# Improved data persistence functions
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

def save_to_local(new_row):
    file_path = "data/local_disease_data.csv"

    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])

    df.to_csv(file_path, index=False)



#----------------------------
# Adding unique ID


def get_next_sample_id():
    file_path = "data/local_disease_data.csv"

    try:
        df = pd.read_csv(file_path)

        if "sample_id" in df.columns and not df.empty:
            last_id = df["sample_id"].iloc[-1]
            # Extract number from SARDI25001
            match = re.search(r"SARDI(\d+)", str(last_id))
            if match:
                next_num = int(match.group(1)) + 1
            else:
                next_num = 25001
        else:
            next_num = 25001
    except FileNotFoundError:
        next_num = 25001

    return f"SARDI{next_num:05d}"

# -------------------------------
# Load data with caching
# -------------------------------
# Load data with caching (LOCAL ONLY)
@st.cache_data(ttl=300)
def load_data():
    df_local = load_local_data()

    if df_local.empty:
        return pd.DataFrame()

    # --- Fix date parsing ---
    if "date" in df_local.columns:
        df_local["date"] = pd.to_datetime(
            df_local["date"],
            errors="coerce",
            dayfirst=True
        )

    # Drop duplicates if same survey got appended
    df_local = df_local.drop_duplicates()

    return df_local


    # Combine both
    if not df_local.empty and not df_main.empty:
        df_combined = pd.concat([df_main, df_local], ignore_index=True)
    elif not df_local.empty:
        df_combined = df_local
    elif not df_main.empty:
        df_combined = df_main
    else:
        return pd.DataFrame()

    # --- Fix date parsing ---
    if "date" in df_combined.columns:
        # Try both common formats
        df_combined["date"] = pd.to_datetime(
            df_combined["date"],
            errors="coerce",
            dayfirst=False,  # remote CSV often uses ISO format
        )
        # If still NaT, try fallback parsing
        if df_combined["date"].isna().any():
            df_combined["date"] = pd.to_datetime(
                df_combined["date"],
                errors="coerce",
                dayfirst=True
            )

    # Drop duplicates if same survey got appended
    df_combined = df_combined.drop_duplicates()

    return df_combined

# Initialize session state
if "df" not in st.session_state:
    st.session_state.df = load_data()

def reload_data():
    st.cache_data.clear()
    st.session_state.df = load_data()
    st.success("Data reloaded!")

# -------------------------------
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
st.markdown(sidebar_mobile_friendly, unsafe_allow_html=True)

st.sidebar.markdown("## 🌾 South Australia Disease Surveillance")
menu = st.sidebar.radio("Navigation", ["Disease tracker", "Tag a disease", "About", "Resources"])

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
    required_columns = ["sample_id", "date", "crop", "disease1", "severity1_percent", "latitude", "longitude", "survey_location"]
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
    mask = (df["date"] >= pd.to_datetime(date_range[0])) & (df["date"] <= pd.to_datetime(date_range[1]))
    if crop != "All":
        mask &= df["crop"] == crop
    if disease != "All":
        mask &= df["disease1"] == disease

    df_filtered = df.loc[mask]

    # Metrics
    st.markdown("### Key Metrics")
    if not df_filtered.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Surveys", len(df_filtered))
        col2.metric("Max Severity (%)", int(df_filtered["severity1_percent"].max()))
        col3.metric("Average Severity (%)", round(df_filtered["severity1_percent"].mean(), 1))
    else:
        st.warning("No data found for the selected filters.")

    # Create tabs for Map and Graph
    tab1, tab2 = st.tabs(["🗺️ Map", "📊 Graph"])
    with tab1:
        st.markdown("### Map View")
    
        unique_diseases = df["disease1"].dropna().unique()
        disease_colors = px.colors.qualitative.Set3[:len(unique_diseases)]
        disease_color_map = dict(zip(unique_diseases, disease_colors))
    
        # Create the map only once
        m = folium.Map(location=[-36.76, 142.21], zoom_start=6)
    
        # Add markers
        for _, row in df_filtered.iterrows():
            if not pd.isna(row["latitude"]) and not pd.isna(row["longitude"]):
                popup_text = f"{row.get('survey_location', 'Unknown')}"
    
                if not pd.isna(row.get("disease1")):
                    if not pd.isna(row.get("severity1_percent")):
                        popup_text += f" | Disease1: {row['disease1']} ({row['severity1_percent']}%)"
                    else:
                        popup_text += f" | Disease1: {row['disease1']}"
    
                if not pd.isna(row.get("disease2")) and row["disease2"] != "":
                    if not pd.isna(row.get("severity2_percent")):
                        popup_text += f" | Disease2: {row['disease2']} ({row['severity2_percent']}%)"
                    else:
                        popup_text += f" | Disease2: {row['disease2']}"
                        
                if not pd.isna(row.get("disease3")) and row["disease3"] != "":
                    if not pd.isna(row.get("severity3_percent")):
                        popup_text += f" | Disease3: {row['disease3']} ({row['severity3_percent']}%)"
                    else:
                        popup_text += f" | Disease3: {row['disease3']}"
    
                color = disease_color_map.get(row["disease1"], "gray")
                folium.CircleMarker(
                    location=[row["latitude"], row["longitude"]],
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
            
            fig = px.bar(
                df_filtered,
                x=x_col,
                y="severity1_percent",
                title=title,
                labels={"severity1_percent": "Severity (%)", x_col: x_axis},
                color="disease1",
                color_discrete_map=disease_color_map,
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
            st.dataframe(df_filtered[["sample_id", "date", "crop", "disease1", "survey_location", "severity1_percent"]])
        
        st.download_button(
            "Download CSV",
            df_filtered.to_csv(index=False).encode("utf-8"),
            "survey.csv",
            "text/csv",
        )
    else:
        st.info("No data available for the selected filters.")

    st.markdown("### 📸 Download Photos")
    
    # Filter only rows with photos
    df_photos = df_filtered[df_filtered["photo_filename"].notna() & (df_filtered["photo_filename"] != "")]
    
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
            sample_id = get_next_sample_id()
        
            photo_url = ""
            if uploaded_file is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_extension = uploaded_file.name.split(".")[-1]
                photo_filename = f"disease_photo_{timestamp}.{file_extension}"
                photo_url = save_photo_to_github(uploaded_file.getbuffer(), photo_filename)
        
            new_record = {
                "sample_id": sample_id,
                "date": date.strftime("%d/%m/%Y"),
                "collector_name": collector,
                "field_type": field_type,
                "Agronomist": agronomist,
                "crop": crop,
                "variety": variety,
                "plant_stage": plant_stage,
                "disease1": disease1,
                "disease2": disease2 if disease2 != "None" else "",
                "disease3": disease3 if disease3 != "None" else "",
                "severity1_percent": severity1,
                "severity2_percent": severity2 if disease2 != "None" else 0,
                "severity3_percent": severity3 if disease3 != "None" else 0,
                "latitude": float(latitude) if latitude else -36.76,
                "longitude": float(longitude) if longitude else 142.21,
                "survey_location": location,
                "photo_url": photo_url,   # store permanent GitHub link
                "field_notes": field_notes,
            }
        
            # Load existing data (from GitHub)
            df_existing = pd.read_csv("https://raw.githubusercontent.com/pullanagari/Disease_app/main/data_temp.csv")
            df_updated = pd.concat([df_existing, pd.DataFrame([new_record])], ignore_index=True)
        
            if save_csv_to_github(df_updated):
                st.success("✅ Submission saved to GitHub permanently")
                reload_data()
                if photo_url:
                    st.image(photo_url, caption="Uploaded to GitHub")


        # if submitted:
        #     sample_id = get_next_sample_id()
        #     # Validate required fields
        #     if not all([crop, disease1, location]):
        #         st.error("Please fill in all required fields: Crop, Disease 1, and Location")
        #     else:
        #         photo_filename = None
        #         if uploaded_file is not None:
        #             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        #             file_extension = uploaded_file.name.split(".")[-1]
        #             photo_filename = f"disease_photo_{timestamp}.{file_extension}"
        #             with open(os.path.join("uploads", photo_filename), "wb") as f:
        #                 f.write(uploaded_file.getbuffer())

        #         if disease2 == "None":
        #             disease2 = ""
        #             severity2 = 0
        #         if disease3 == "None":
        #             disease3 = ""
        #             severity3 = 0

        #         new_record = {
        #             "sample_id": sample_id,
        #             "date": date.strftime("%d/%m/%Y"),
        #             "collector_name": collector,
        #             "field_type": field_type,
        #             "Agronomist": agronomist,
        #             "crop": crop,
        #             "variety": variety,
        #             "plant_stage": plant_stage,
        #             "disease1": disease1,
        #             "disease2": disease2,
        #             "disease3": disease3,
        #             "severity1_percent": severity1,
        #             "severity2_percent": severity2,
        #             "severity3_percent": severity3,
        #             "latitude": float(latitude) if latitude else -36.76,
        #             "longitude": float(longitude) if longitude else 142.21,
        #             "survey_location": location,
        #             "photo_filename": photo_filename if photo_filename else "",
        #             "field_notes": field_notes,
        #         }

        #         # Load existing local data
        #         local_data = load_local_data()
                
        #         # Append new record
        #         new_df = pd.DataFrame([new_record])
        #         if local_data.empty:
        #             updated_data = new_df
        #         else:
        #             updated_data = pd.concat([local_data, new_df], ignore_index=True)
                
        #         # Save updated data
        #         if save_local_data(updated_data):
        #             st.success("✅ Submission successful! Data saved to local storage.")
                    
        #             # Clear cache and reload data
        #             reload_data()
                    
        #             if uploaded_file is not None:
        #                 st.markdown("**Uploaded Photo Preview:**")
        #                 image = Image.open(uploaded_file)
        #                 st.image(image, caption="Disease Photo", use_column_width=True)
        #         else:
        #             st.error("Failed to save data. Please try again.")

  


# -------------------------------
# About Page
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

















