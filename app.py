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
# import flush_database



# -------------------------------

st.set_page_config(
    page_title="South Australia Disease Surveillance",
    layout="wide",
    initial_sidebar_state="expanded"
)

# loading old data

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


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    try:
        df_main = pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Error loading remote data: {e}")
        df_main = pd.DataFrame()

    df_local = load_local_data()
    
    if not df_local.empty and not df_main.empty:
        df_combined = pd.concat([df_main, df_local], ignore_index=True)
    elif not df_local.empty:
        df_combined = df_local
    elif not df_main.empty:
        df_combined = df_main
    else:
        df_combined = pd.DataFrame()

    if not df_combined.empty:
        df_combined["date"] = pd.to_datetime(df_combined["date"], errors="coerce", dayfirst=True)
    
    return df_combined

# Initialize session state
if "df" not in st.session_state:
    st.session_state.df = load_data()

def reload_data():
    st.cache_data.clear()
    st.session_state.df = load_data()
    st.success("Data reloaded!")


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
            st.dataframe(df_filtered[["date", "crop", "disease1", "survey_location", "severity1_percent"]])
        
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
        # plant_stage = st.selectbox(
        #     "Plant Growth Stage",
        #     ["Emergence", "Tillering", "Stem elongation", "Flowering", "Grain filling", "Maturity"],
        # )
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
                photo_filename = None
                if uploaded_file is not None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = uploaded_file.name.split(".")[-1]
                    photo_filename = f"disease_photo_{timestamp}.{ext}"
                    with open(os.path.join("uploads", photo_filename), "wb") as f:
                        f.write(uploaded_file.getbuffer())

                if disease2 == "None": disease2, severity2 = "", 0
                if disease3 == "None": disease3, severity3 = "", 0

                new_record = {
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
                }

                # Load existing local data
                local_data = load_local_data()
                updated_data = pd.concat([local_data, pd.DataFrame([new_record])], ignore_index=True) if not local_data.empty else pd.DataFrame([new_record])

                if save_local_data(updated_data):
                    st.success("✅ Submission successful! Data saved locally.")
                    reload_data()
                    if uploaded_file:
                        st.image(Image.open(uploaded_file), caption="Disease Photo", use_column_width=True)
                else:
                    st.error("Failed to save data. Please try again.")
   

    st.markdown("---")
    # st.markdown("### Export Data")
    # local_data = load_local_data()
    # if not local_data.empty:
    #     st.download_button(
    #         "Download All Local Data",
    #         local_data.to_csv(index=False).encode("utf-8"),
    #         "local_disease_data.csv",
    #         "text/csv",
    #         key="download-csv",
    #     )
    #     st.markdown("### Local Data Entries")
    #     st.dataframe(local_data)
    # else:
    #     st.info("No local data entries yet.")


# -------------------------------
# About Page
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


# Hide Streamlit top-right menu + footer
custom_css = """
<style>
/* Hide top-right menu */
div[data-testid="stToolbar"] {visibility: hidden;}

/* Hide footer */
div[data-testid="stFooter"] {visibility: hidden;}

/* Hide sidebar collapse button (optional) */
button[data-testid="stSidebarCollapseButton"] {display: none;}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)














