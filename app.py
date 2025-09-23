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
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import mimetypes

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
# Google Drive Integration
@st.cache_resource
def get_drive_service():
    """Return an authorized Google Drive service client"""
    try:
        SCOPES = ["https://www.googleapis.com/auth/drive.file"]
        
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
        elif os.path.exists("service_account.json"):
            creds = service_account.Credentials.from_service_account_file(
                "service_account.json", scopes=SCOPES
            )
        else:
            st.error("No Google Drive credentials found")
            return None

        drive_service = build('drive', 'v3', credentials=creds)
        return drive_service
    except Exception as e:
        st.error(f"❌ Google Drive auth error: {e}")
        return None

def create_drive_folder(service, folder_name, parent_id=None):
    """Create a folder in Google Drive and return its ID"""
    try:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    except Exception as e:
        st.error(f"Error creating folder: {e}")
        return None

def get_disease_photos_folder(service):
    """Get the ID of the shared Disease_Surveillance_Photos folder"""
    try:
        # Replace this with the exact folder name in your personal Drive
        folder_name = "Disease_Surveillance_Photos"

        # Search for the folder
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])

        if folders:
            # Folder exists, return its ID
            return folders[0]['id']
        else:
            # Folder not found, inform the user
            st.error(f"Folder '{folder_name}' not found. Please share it with the service account.")
            return None

    except Exception as e:
        st.error(f"Error accessing Disease_Surveillance_Photos folder: {e}")
        return None


def upload_to_drive(service, file_path, file_name, folder_id):
    """Upload a file to Google Drive and return the file ID"""
    try:
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, 
                              mimetype=mimetypes.guess_type(file_path)[0] or 'image/jpeg')
        
        file = service.files().create(body=file_metadata,
                                    media_body=media,
                                    fields='id, webViewLink').execute()
        
        return file.get('id'), file.get('webViewLink')
    except Exception as e:
        st.error(f"Error uploading to Google Drive: {e}")
        return None, None

def save_photo_to_drive(photo_path, photo_filename):
    try:
        service = get_drive_service()
        if not service:
            st.error("Google Drive service not available")
            return None, None

        folder_id = get_or_create_disease_photos_folder(service)
        if not folder_id:
            st.error("Could not find or create Disease_Surveillance_Photos folder")
            return None, None

        file_metadata = {
            "name": photo_filename,
            "parents": [folder_id],
        }
        media = MediaFileUpload(photo_path, mimetype=mimetypes.guess_type(photo_path)[0] or 'image/jpeg')

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        file_id = uploaded_file.get("id")
        file_link = uploaded_file.get("webViewLink")  # Only accessible via the service account

        return file_id, file_link

    except Exception as e:
        st.error(f"Error saving photo to Google Drive: {e}")
        return None, None



# -------------------------------
# Google Sheets Integration (updated to include drive_photo_id)
@st.cache_resource
def get_gs_client():
    """Return an authorized gspread client (cached)"""
    try:
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
        elif os.path.exists("service_account.json"):
            creds = service_account.Credentials.from_service_account_file(
                "service_account.json", scopes=SCOPES
            )
        else:
            st.error("No Google Sheets credentials found")
            return None

        client = gspread.authorize(creds)
        return client

    except Exception as e:
        st.error(f"❌ Google Sheets auth error: {e}")
        return None

def get_spreadsheet():
    """Return spreadsheet object if available"""
    client = get_gs_client()
    if not client:
        return None

    SHEET_ID = "15D6_hA_LhG6M8CKMUFikCxXPQNtxhNBSCykaBF2egtE"
    try:
        spreadsheet = client.open_by_key(SHEET_ID)
        st.success("✅ Connected to Google Sheets")
        return spreadsheet
    except Exception as e:
        st.error(f"❌ Error opening Google Sheet: {e}")
        return None

def save_to_google_sheets(new_row: dict):
    """Save data to Google Sheets with proper error handling"""
    try:
        spreadsheet = get_spreadsheet()
        if not spreadsheet:
            st.warning("⚠️ No cloud data available for synchronization.")
            return False

        worksheet = spreadsheet.sheet1
        existing_values = worksheet.get_all_values()
        
        # Add headers if sheet is empty
        if not existing_values:
            headers = list(new_row.keys())
            worksheet.append_row(headers)
        
        # Append row values (convert all to strings)
        values = [str(v) for v in new_row.values()]
        worksheet.append_row(values, value_input_option="USER_ENTERED")
        
        st.success("✅ Data saved to Google Sheets")
        return True
        
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {e}")
        return False

def load_from_google_sheets():
    """Load all data from Google Sheets"""
    spreadsheet = get_spreadsheet()
    if spreadsheet:
        try:
            worksheet = spreadsheet.sheet1
            records = worksheet.get_all_records()
            if records:
                return pd.DataFrame(records)
        except Exception as e:
            st.error(f"Error loading from Google Sheets: {e}")
    return pd.DataFrame()

# -------------------------------
# Data persistence functions (updated for drive_photo_id)
def get_local_data_path():
    return os.path.join("data", "local_disease_data.csv")

def save_local_data(df):
    try:
        local_path = get_local_data_path()
        df.to_csv(local_path, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

def load_local_data():
    local_path = get_local_data_path()
    if os.path.exists(local_path):
        try:
            return pd.read_csv(local_path)
        except Exception as e:
            st.error(f"Error loading local data: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def save_data(new_row):
    """Save data to both local storage and Google Sheets"""
    # First save to Google Sheets
    gs_success = save_to_google_sheets(new_row)
    
    # Then save to local storage as backup
    file_path = "data/local_disease_data.csv"
    
    try:
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df = pd.DataFrame([new_row])
        
        df.to_csv(file_path, index=False)
        local_success = True
    except Exception as e:
        st.error(f"Error saving to local storage: {e}")
        local_success = False
    
    return gs_success or local_success

# -------------------------------
# Unique ID generation
def get_next_sample_id():
    """Generate the next sample ID by checking both local and Google Sheets data"""
    # First check Google Sheets for the latest ID
    gs_data = load_from_google_sheets()
    if not gs_data.empty and "sample_id" in gs_data.columns:
        last_id = gs_data["sample_id"].iloc[-1]
        match = re.search(r"SARDI(\d+)", str(last_id))
        if match:
            next_num = int(match.group(1)) + 1
        else:
            next_num = 25001
    else:
        # Fallback to local file
        file_path = "data/local_disease_data.csv"
        try:
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                if "sample_id" in df.columns and not df.empty:
                    last_id = df["sample_id"].iloc[-1]
                    match = re.search(r"SARDI(\d+)", str(last_id))
                    if match:
                        next_num = int(match.group(1)) + 1
                    else:
                        next_num = 25001
                else:
                    next_num = 25001
            else:
                next_num = 25001
        except:
            next_num = 25001
    
    return f"SARDI{next_num:05d}"

# -------------------------------
# Load data with caching
def load_data():
    """Load data from both local storage and Google Sheets, merge them"""
    df_local = load_local_data()
    df_gs = load_from_google_sheets()
    
    if df_local.empty and df_gs.empty:
        return pd.DataFrame()
    
    # Combine both data sources
    if not df_local.empty and not df_gs.empty:
        df_combined = pd.concat([df_gs, df_local], ignore_index=True)
        # Remove duplicates based on sample_id
        df_combined = df_combined.drop_duplicates(subset=['sample_id'], keep='last')
    elif not df_local.empty:
        df_combined = df_local
    else:
        df_combined = df_gs
    
    # Fix date parsing
    if "date" in df_combined.columns:
        df_combined["date"] = pd.to_datetime(
            df_combined["date"],
            errors="coerce",
            dayfirst=True
        )
    
    return df_combined

# Initialize session state
if "df" not in st.session_state:
    st.session_state.df = load_data()

def reload_data():
    st.cache_data.clear()
    st.session_state.df = load_data()
    st.success("Data reloaded!")

# Debug code to check authentication
if st.sidebar.button("Debug Google Sheets Connection"):
    client = get_gs_client()
    if client:
        try:
            spreadsheet = client.open_by_key("15D6_hA_LhG6M8CKMUFikCxXPQNtxhNBSCykaBF2egtE")
            st.sidebar.success("✅ Successfully connected to Google Sheets")
            worksheet = spreadsheet.sheet1
            records = worksheet.get_all_records()
            st.sidebar.write(f"Found {len(records)} records in sheet")
        except Exception as e:
            st.sidebar.error(f"Error accessing sheet: {e}")
    else:
        st.sidebar.error("Failed to create client")

# -------------------------------
# UI and rest of the application remains the same
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
menu = st.sidebar.radio("Navigation", ["Disease tracker", "Tag a disease", "About", "Resources", "Data Management"])

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
        col1, col2 = st.columns(2)
        
        with col1:
            # Download all photos as ZIP (local files)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for _, row in df_photos.iterrows():
                    photo_path = os.path.join("uploads", row["photo_filename"])
                    if os.path.exists(photo_path):
                        zf.write(photo_path, arcname=row["photo_filename"])
            st.download_button(
                "Download Local Photos (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="disease_photos_local.zip",
                mime="application/zip",
            )
        
        with col2:
            # Show Google Drive links
            st.markdown("**Google Drive Photos:**")
            for _, row in df_photos.iterrows():
                if row.get("drive_photo_link"):
                    st.markdown(f"- [{row['photo_filename']}]({row['drive_photo_link']})")
                elif row.get("drive_photo_id"):
                    st.markdown(f"- {row['photo_filename']} (Drive ID: {row['drive_photo_id']})")
                else:
                    st.markdown(f"- {row['photo_filename']} (Local only)")

    else:
        st.info("No photos available for the selected filters.")


# -------------------------------
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
            disease_options = ["Stripe rust", "Leaf rust", "Stem rust", "Septoria tritici blotch", "Yellow leaf spot", 
                               "Powdery mildew", "Eye spot", "Black point", "Smut", "Spot form net blotch", 
                               "Net form net blotch", "Scald", "Red Leather Leaf", "Septoria avenae blotch", 
                               "Bacterial blight", "Ascochyta Blight", "Botrytis Grey Mold", "Sclerotinia white mould", 
                               "Chocolate Spot", "Cercospora leaf spot", "Downy mildew", "Black Spot", 
                               "Root Disease", "Virus", "Blackleg", "Other"]
            
            disease1 = st.selectbox("Disease 1", disease_options)
            disease2 = st.selectbox("Disease 2", ["None"] + disease_options)
            disease3 = st.selectbox("Disease 3", ["None"] + disease_options)
            
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
            # Validate required fields
            if not all([crop, disease1, location]):
                st.error("Please fill in all required fields: Crop, Disease 1, and Location")
            else:            
                photo_filename = None
                drive_photo_id = None
                drive_photo_link = None
                
                if uploaded_file is not None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_extension = uploaded_file.name.split(".")[-1]
                    photo_filename = f"disease_photo_{timestamp}.{file_extension}"
                    local_file_path = os.path.join("uploads", photo_filename)
                    
                    # Save locally
                    with open(local_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Also save to Google Drive
                    drive_photo_id, drive_photo_link = save_photo_to_drive(local_file_path, photo_filename)
                    
                    if drive_photo_id:
                        st.success(f"✅ Photo saved to Google Drive (ID: {drive_photo_id})")
                    else:
                        st.warning("⚠️ Photo saved locally but failed to upload to Google Drive")
        
                if disease2 == "None":
                    disease2 = ""
                    severity2 = 0
                if disease3 == "None":
                    disease3 = ""
                    severity3 = 0

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
                    "disease2": disease2,
                    "disease3": disease3,
                    "severity1_percent": severity1,
                    "severity2_percent": severity2,
                    "severity3_percent": severity3,
                    "latitude": float(latitude) if latitude else -36.76,
                    "longitude": float(longitude) if longitude else 142.21,
                    "survey_location": location,
                    "photo_filename": photo_filename if photo_filename else "",
                    "drive_photo_id": drive_photo_id if drive_photo_id else "",
                    "drive_photo_link": drive_photo_link if drive_photo_link else "",
                    "field_notes": field_notes,
                }

                # Save data to both local storage and Google Sheets
                if save_data(new_record):
                    st.success("✅ Submission successful! Data saved to persistent storage.")
                    
                    # Clear cache and reload data
                    reload_data()

                    if uploaded_file is not None:
                        st.markdown("**Uploaded Photo Preview:**")
                        image = Image.open(io.BytesIO(uploaded_file.getbuffer()))
                        st.image(image, caption="Disease Photo", use_column_width=True)
                        
                        # Show Google Drive link if available
                        if drive_photo_link:
                            st.markdown(f"**Google Drive Link:** [View Photo]({drive_photo_link})")
                   
                else:
                    st.error("Failed to save data. Please try again.")

                
# -------------------------------
# Data Management Page
elif menu == "Data Management":
    st.markdown("## 📊 Data Management")
    
    st.info("This section allows you to manage your data storage options.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Local Data")
        if os.path.exists(get_local_data_path()):
            local_df = pd.read_csv(get_local_data_path())
            st.write(f"Local records: {len(local_df)}")
            st.download_button(
                "Download Local Data",
                local_df.to_csv(index=False).encode("utf-8"),
                "local_disease_data.csv",
                "text/csv",
            )
            
            if st.button("Clear Local Data"):
                os.remove(get_local_data_path())
                st.success("Local data cleared!")
                reload_data()
        else:
            st.write("No local data found.")
    
    with col2:
        st.markdown("### Cloud Data (Google Sheets)")
        gs_data = load_from_google_sheets()
        if not gs_data.empty:
            st.write(f"Cloud records: {len(gs_data)}")
            st.download_button(
                "Download Cloud Data",
                gs_data.to_csv(index=False).encode("utf-8"),
                "cloud_disease_data.csv",
                "text/csv",
            )
            
            # Add a button to open the Google Sheet
            if st.button("Open Google Sheet"):
                st.markdown("[Open Google Sheet in Browser](https://docs.google.com/spreadsheets/d/your-sheet-id-here)")
        else:
            st.write("No cloud data found or not configured.")
            
            
    
    st.markdown("### Synchronize Data")
    if st.button("Synchronize Local with Cloud"):
        try:
            gs_data = load_from_google_sheets()
            if not gs_data.empty:
                # Save cloud data to local
                save_local_data(gs_data)
                st.success("Local data updated from cloud!")
                reload_data()
            else:
                st.warning("No cloud data available for synchronization.")
        except Exception as e:
            st.error(f"Error during synchronization: {e}")


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
    - Google Sheets integration for persistent data storage
    - Improved data management  

    **Tips:**  
    - Use the 'Refresh Data' button in the sidebar to see newly submitted entries  
    - If data doesn't update automatically, try refreshing the page
    
    **Data Persistence:**
    - Your submitted data is now saved to both local storage and Google Sheets
    - Google Sheets ensures your data persists across sessions and deployments
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





























