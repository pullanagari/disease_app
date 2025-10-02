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


@st.cache_resource
def get_gs_client():
    """Return an authorized gspread client (cached)"""
    try:
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Check for credentials in Streamlit secrets (for cloud deployment)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=SCOPES
            )
        # Check for service account file (for local development)
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
        return spreadsheet
    except Exception as e:
        st.error(f"❌ Error opening Google Sheet: {e}")
        return None

def init_google_sheets():
    """Initialize connection to Google Sheets using service account"""
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
        else:
            creds = service_account.Credentials.from_service_account_file(
                "service_account.json", scopes=SCOPES
            )

        client = gspread.authorize(creds)
        SHEET_ID = "15D6_hA_LhG6M8CKMUFikCxXPQNtxhNBSCykaBF2egtE"
        spreadsheet = client.open_by_key(SHEET_ID)
        return spreadsheet

    except Exception as e:
        st.error(f"❌ Google Sheets error: {e}")
        st.warning("⚠️ No cloud data available for synchronization. Using local storage.")
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
    
    return gs_success or local_success  # Return True if either save was successful

#----------------------------
# Adding unique ID
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
@st.cache_data(ttl=300)
@st.cache_data(ttl=300)
def load_data():
    """Load the most recent data, prioritizing Google Sheets but merging with local if needed."""
    df_local = pd.DataFrame()
    df_gs = pd.DataFrame()

    # Try load from Google Sheets
    try:
        df_gs = load_from_google_sheets()
        if not df_gs.empty:
            # Save cloud data to local as backup
            save_local_data(df_gs)
    except Exception as e:
        st.warning(f"⚠️ Could not load from Google Sheets: {e}")

    # Try load from local
    df_local = load_local_data()

    # --- Merge logic ---
    if df_local.empty and df_gs.empty:
        return pd.DataFrame()

    if not df_local.empty and not df_gs.empty:
        df_combined = pd.concat([df_gs, df_local], ignore_index=True)
        if "sample_id" in df_combined.columns:
            df_combined = df_combined.drop_duplicates(subset=["sample_id"], keep="last")
    elif not df_local.empty:
        df_combined = df_local
    else:
        df_combined = df_gs

    # --- Robust date parsing ---
    date_columns = [col for col in df_combined.columns if 'date' in col.lower()]
    
    for date_col in date_columns:
        if date_col in df_combined.columns:
            # Try multiple date formats
            try:
                df_combined[date_col] = pd.to_datetime(
                    df_combined[date_col], 
                    errors='coerce', 
                    dayfirst=True,
                    format='mixed'
                )
            except:
                try:
                    # Try different parsing approach
                    df_combined[date_col] = pd.to_datetime(
                        df_combined[date_col], 
                        errors='coerce'
                    )
                except:
                    st.warning(f"Could not parse date column: {date_col}")
            
            # If still not datetime, try manual conversion
            if not pd.api.types.is_datetime64_any_dtype(df_combined[date_col]):
                try:
                    df_combined[date_col] = pd.to_datetime(
                        df_combined[date_col].astype(str), 
                        errors='coerce',
                        dayfirst=True
                    )
                except:
                    pass

    return df_combined

# Initialize session state
if "df" not in st.session_state:
    st.session_state.df = load_data()

def reload_data():
    """Force reload data from all sources"""
    try:
        # Clear all relevant caches
        st.cache_data.clear()
        
        # Reload data
        new_data = load_data()
        
        # Ensure date columns are properly formatted
        date_columns = [col for col in new_data.columns if 'date' in col.lower()]
        for date_col in date_columns:
            if date_col in new_data.columns:
                if not pd.api.types.is_datetime64_any_dtype(new_data[date_col]):
                    new_data[date_col] = pd.to_datetime(new_data[date_col], errors='coerce')
        
        st.session_state.df = new_data
        
        st.success("Data reloaded successfully!")
        st.rerun()  # Force UI refresh
    except Exception as e:
        st.error(f"Error reloading data: {e}")

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
# Disease Tracker Page - FIXED VERSION
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
        col1.metric("Total Surveys", len(df))
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
        m = folium.Map(location=[-34.96, 138.63], zoom_start=6)
    
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
        
    if not df.empty:
        # Option to show all columns or just selected ones
        show_all_columns = st.checkbox("Show all columns", value=False)
        
        # Create a working copy of the dataframe for editing
        if show_all_columns:
            editable_df = df.copy()
        else:
            # Select only the columns that exist in the dataframe
            available_columns = ["sample_id", "date", "crop", "disease1", "survey_location", "severity1_percent"]
            existing_columns = [col for col in available_columns if col in df.columns]
            editable_df = df[existing_columns].copy()
        
        # Ensure date column is in proper format for editing
        if 'date' in editable_df.columns:
            # Convert to datetime if not already
            if not pd.api.types.is_datetime64_any_dtype(editable_df['date']):
                editable_df['date'] = pd.to_datetime(editable_df['date'], errors='coerce')
            # Format for display in the editor
            editable_df['date'] = editable_df['date'].dt.strftime('%d/%m/%Y')
    
        # Make table editable - use a unique key for the data_editor
        edited_df = st.data_editor(
            editable_df,
            num_rows="dynamic",
            use_container_width=True,
            key="surveillance_summary_editor",
        )
    
        # Save edited changes
        if st.button("💾 Save Changes"):
            try:
                # Create a complete updated dataframe with all changes
                if show_all_columns:
                    updated_df = edited_df.copy()
                else:
                    # Merge changes back into the full dataframe
                    updated_df = df.copy()
                    for col in edited_df.columns:
                        if col in updated_df.columns:
                            # Update only the columns that were edited
                            if col == 'date':
                                # Handle date conversion properly
                                updated_df[col] = pd.to_datetime(edited_df[col], format='%d/%m/%Y', errors='coerce')
                            else:
                                updated_df[col] = edited_df[col]
                
                # Ensure date column is properly formatted in the final dataframe
                if 'date' in updated_df.columns:
                    if not pd.api.types.is_datetime64_any_dtype(updated_df['date']):
                        updated_df['date'] = pd.to_datetime(updated_df['date'], errors='coerce')
                
                # Update session state
                st.session_state.df = updated_df
                
                # Save to local storage
                save_local_data(st.session_state.df)
                
                # Save to Google Sheets
                try:
                    spreadsheet = get_spreadsheet()
                    if spreadsheet:
                        worksheet = spreadsheet.sheet1
                        
                        # Clear the entire worksheet
                        worksheet.clear()
                        
                        # Prepare data for Google Sheets - ensure proper date formatting
                        gs_df = st.session_state.df.copy()
                        if 'date' in gs_df.columns:
                            gs_df['date'] = gs_df['date'].dt.strftime('%d/%m/%Y')
                        
                        # Add headers
                        worksheet.append_row(gs_df.columns.tolist())
                        
                        # Add all data rows
                        if not gs_df.empty:
                            # Convert all values to strings and handle NaN/None
                            data_rows = []
                            for _, row in gs_df.iterrows():
                                row_values = []
                                for val in row:
                                    if pd.isna(val):
                                        row_values.append("")
                                    else:
                                        row_values.append(str(val))
                                data_rows.append(row_values)
                            
                            worksheet.append_rows(data_rows, value_input_option="USER_ENTERED")
                        
                        st.success("✅ Changes saved to Google Sheets and local storage!")
                        
                        # Force reload from cloud to ensure consistency
                        reload_data()
                        
                    else:
                        st.warning("⚠️ Could not connect to Google Sheets, saved only locally.")
                except Exception as e:
                    st.error(f"❌ Error saving to Google Sheets: {e}")
                    st.info("Data saved to local storage only.")
                    
            except Exception as e:
                st.error(f"Error processing changes: {e}")

        # Row deletion section
        st.markdown("### Delete Records")
        rows_to_delete = st.multiselect(
            "Select rows to delete (by Sample ID)",
            options=edited_df["sample_id"].tolist(),
        )
        
        if st.button("🗑 Delete Selected Rows"):
            if rows_to_delete:
                # Remove from session state
                st.session_state.df = st.session_state.df[~st.session_state.df["sample_id"].isin(rows_to_delete)]
                
                # Save to local
                save_local_data(st.session_state.df)
                
                # Save to Google Sheets
                try:
                    spreadsheet = get_spreadsheet()
                    if spreadsheet:
                        worksheet = spreadsheet.sheet1
                        worksheet.clear()
                        
                        # Prepare data for Google Sheets - ensure proper date formatting
                        gs_df = st.session_state.df.copy()
                        if 'date' in gs_df.columns:
                            gs_df['date'] = gs_df['date'].dt.strftime('%d/%m/%Y')
                        
                        worksheet.append_row(gs_df.columns.tolist())
                        
                        if not gs_df.empty:
                            data_rows = []
                            for _, row in gs_df.iterrows():
                                row_values = []
                                for val in row:
                                    if pd.isna(val):
                                        row_values.append("")
                                    else:
                                        row_values.append(str(val))
                                data_rows.append(row_values)
                            
                            worksheet.append_rows(data_rows, value_input_option="USER_ENTERED")
                        
                        st.success(f"✅ Deleted {len(rows_to_delete)} record(s) from both local and cloud storage!")
                        
                        # Force reload
                        reload_data()
                    else:
                        st.warning("⚠️ Could not connect to Google Sheets, deleted from local storage only.")
                except Exception as e:
                    st.error(f"Error deleting from Google Sheets: {e}")
            else:
                st.warning("Please select at least one record to delete.")
    
        # Download option - ensure proper date formatting in download
        download_df = st.session_state.df.copy()
        if 'date' in download_df.columns and pd.api.types.is_datetime64_any_dtype(download_df['date']):
            download_df['date'] = download_df['date'].dt.strftime('%d/%m/%Y')
            
        st.download_button(
            "⬇️ Download CSV",
            download_df.to_csv(index=False).encode("utf-8"),
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
# Tag a Disease Page - FIXED VERSION
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
                         "Vetch","Field peas","Chickpea", "Other"]
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

            disease1 = st.selectbox("Disease 1",["None"]+ disease_options)
            disease2 = st.selectbox("Disease 2", ["None"] + disease_options)
            disease3 = st.selectbox("Disease 3", ["None"] + disease_options)
            
            severity1 = st.number_input("Severity 1 (%)", min_value=0, max_value=100, value=0, step=1)
            severity2 = st.number_input("Severity 2 (%)", min_value=0, max_value=100, value=0, step=1)
            severity3 = st.number_input("Severity 3 (%)", min_value=0, max_value=100, value=0, step=1)
            
            latitude = st.text_input("Latitude", "-34.96")
            longitude = st.text_input("Longitude", "138.63")

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
                if uploaded_file is not None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_extension = uploaded_file.name.split(".")[-1]
                    photo_filename = f"disease_photo_{timestamp}.{file_extension}"
                    with open(os.path.join("uploads", photo_filename), "wb") as f:
                        f.write(uploaded_file.getbuffer())
        
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
                    "latitude": float(latitude) if latitude else -34.96,
                    "longitude": float(longitude) if longitude else 138.63,
                    "survey_location": location,
                    "photo_filename": photo_filename if photo_filename else "",
                    "field_notes": field_notes,
                    "Action": ", ".join(molecular_diagnosis) if molecular_diagnosis else "",  # FIXED: Use correct variable name
                    "sample_taken": sample_taken,
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
                st.markdown("[Open Google Sheet in Browser](https://docs.google.com/spreadsheets/d/15D6_hA_LhG6M8CKMUFikCxXPQNtxhNBSCykaBF2egtE)")
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

