import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os
from PIL import Image

# -------------------------------
# Load CSV
# -------------------------------
csv_url = "https://raw.githubusercontent.com/pullanagari/Disease_app/main/test.csv"

# Create directories if they don't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Function to load data
@st.cache_data
def load_data():
    # Load main CSV from GitHub
    df_main = pd.read_csv(csv_url)
    
    # Load local CSV if it exists
    local_csv_path = "data/local_disease_data.csv"
    if os.path.exists(local_csv_path):
        df_local = pd.read_csv(local_csv_path)
        # Combine both datasets
        df_combined = pd.concat([df_main, df_local], ignore_index=True)
    else:
        df_combined = df_main
    
    # Ensure proper datetime parsing
    df_combined["date"] = pd.to_datetime(df_combined["date"], errors="coerce", dayfirst=True)
    return df_combined

# Load initial data
df = load_data()

# -------------------------------
# Page Layout & Sidebar
# -------------------------------
st.set_page_config(
    page_title="Victoria Disease Surveillance",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.markdown("## 🌾 Victoria Disease Surveillance")
menu = st.sidebar.radio("Navigation", ["Disease tracker", "Tag a disease", "About"])

# -------------------------------
# Disease Tracker Page
# -------------------------------
if menu == "Disease tracker":
    st.markdown("## 🗺 Disease Tracker")
    
    col1, col2, col3 = st.columns([1.5,1,1])
    
    with col1:
        crop = st.selectbox("Choose a Crop", df["crop"].dropna().unique())
    with col2:
        disease = st.selectbox("Choose a Disease", ["All"] + sorted(df["disease1"].dropna().unique()))
    with col3:
        date_range = st.date_input("Select Date Range", [datetime(2020,1,1), datetime.today()])

    # Filter data
    mask = (
        (df["crop"] == crop) &
        (df["date"] >= pd.to_datetime(date_range[0])) &
        (df["date"] <= pd.to_datetime(date_range[1]))
    )
    if disease != "All":
        mask &= (df["disease1"] == disease)
    df_filtered = df.loc[mask]

    # Metrics Cards
    st.markdown("### Key Metrics")
    if not df_filtered.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Surveys", len(df_filtered))
        col2.metric("Max Severity (%)", int(df_filtered["severity1_percent"].max()))
        col3.metric("Average Severity (%)", round(df_filtered["severity1_percent"].mean(),1))

    # Map
    st.markdown("### Map View")
    m = folium.Map(location=[-36.76, 142.21], zoom_start=6)
    for _, row in df_filtered.iterrows():
        if not pd.isna(row["latitude"]) and not pd.isna(row["longitude"]):
            # Fixed: Combined both severity values in a single popup
            popup_text = f"{row['survey_location']} (Severity1: {row['severity1_percent']}%, Severity2: {row.get('severity2_percent', 'N/A')}%)"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=6,
                color="red",
                fill=True,
                fill_color="red",
                popup=popup_text
            ).add_to(m)
    st_folium(m, width=800, height=450)

    # Graph
    st.markdown("### Disease Severity Graph")
    if not df_filtered.empty:
        fig = px.bar(df_filtered, x="survey_location", y="severity1_percent",
                     title=f"{crop} - {disease if disease != 'All' else 'All diseases'}",
                     labels={"severity1_percent": "Severity (%)"},
                     color="severity1_percent", color_continuous_scale="reds")
        st.plotly_chart(fig, use_container_width=True)
    
    # Table
    st.markdown("### Surveillance Summary")
    st.dataframe(df_filtered[["date", "crop", "disease1", "survey_location", "severity1_percent"]])
    st.download_button(
        "Download CSV", df_filtered.to_csv(index=False).encode("utf-8"),
        "survey.csv", "text/csv"
    )

# -------------------------------
# Tag a Disease Page
# -------------------------------
elif menu == "Tag a disease":
    st.markdown("## 📌 Tag a Disease")
    
    with st.form("disease_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date", datetime.today())
            collector = st.selectbox("Collector Name", ["Hari Dadu", "Josh Fanning", "Other"])
            crop = st.selectbox("Crop", ["Wheat", "Barley", "Canola", "Lentil"])
            variety = st.text_input("Variety", "")
        with col2:
            disease1 = st.selectbox("Disease 1", ["Stripe rust", "Leaf rust", "Blackleg"])
            disease2 = st.selectbox("Disease 2", ["Stripe rust", "Leaf rust", "Blackleg"])
            # Fixed: Added distinct labels for severity sliders
            severity1 = st.slider("Severity 1 (%)", 0, 100, 0)
            severity2 = st.slider("Severity 2 (%)", 0, 100, 0)
            latitude = st.number_input("Latitude", value=-36.76, step=0.01)
            longitude = st.number_input("Longitude", value=142.21, step=0.01)
        location = st.text_input("Location (Suburb)")
        field_type = st.text_input("Field Type", "")
        agronomist = st.text_input("Agronomist", "")
        plant_stage = st.selectbox("Plant Growth Stage",["Emergence", "Tillering", "Stem elongation", "Flowering", "Grain filling", "Maturity"])
        
        # Photo upload
        uploaded_file = st.file_uploader("Attach Photo (Optional)", type=['png', 'jpg', 'jpeg'])
        
        submitted = st.form_submit_button("Submit")

        if submitted:
            # Handle photo upload
            photo_filename = None
            if uploaded_file is not None:
                # Generate a unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_extension = uploaded_file.name.split('.')[-1]
                photo_filename = f"disease_photo_{timestamp}.{file_extension}"
                
                # Save the uploaded file
                with open(os.path.join("uploads", photo_filename), "wb") as f:
                    f.write(uploaded_file.getbuffer())
            
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
                "severity1_percent": severity1,
                "severity2_percent": severity2,  # Fixed: Added severity2 field
                "latitude": latitude,
                "longitude": longitude,
                "survey_location": location,
                "photo_filename": photo_filename if photo_filename else ""
            }

            # Append new record to CSV
            new_df = pd.DataFrame([new_record])
            
            # Check if local CSV exists, if not create it with headers
            local_csv_path = "data/local_disease_data.csv"
            if os.path.exists(local_csv_path):
                # Append without header
                new_df.to_csv(local_csv_path, mode='a', header=False, index=False)
            else:
                # Create new file with header
                new_df.to_csv(local_csv_path, mode='w', header=True, index=False)
            
            # Clear cache to reload data with the new entry
            st.cache_data.clear()
            
            st.success("✅ Submission successful! Data saved to CSV.")
            
            # Show preview of uploaded photo if available
            if uploaded_file is not None:
                st.markdown("**Uploaded Photo Preview:**")
                image = Image.open(uploaded_file)
                st.image(image, caption="Disease Photo", use_column_width=True)
    
    # Add export functionality
    st.markdown("---")
    st.markdown("### Export Data")
    
    local_csv_path = "data/local_disease_data.csv"
    if os.path.exists(local_csv_path):
        local_data = pd.read_csv(local_csv_path)
        if not local_data.empty:
            st.download_button(
                "Download All Local Data",
                local_data.to_csv(index=False).encode("utf-8"),
                "local_disease_data.csv",
                "text/csv",
                key='download-csv'
            )
            
            # Show local data
            st.markdown("### Local Data Entries")
            st.dataframe(local_data)
        else:
            st.info("No local data entries yet.")
    else:
        st.info("No local data file exists yet.")

# -------------------------------
# About Page
# -------------------------------
else:
    st.markdown("## ℹ️ About Vic Ds App")
    st.markdown("""
    This application supports field crop pathology staff during surveillance activities to upload disease information 
    and visualize disease severity through maps, graphs, and tables.
    
    **New Features:**
    - Photo attachment capability for disease documentation
    - Local CSV data storage and export functionality
    - Improved data management
    """)

