import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os
from PIL import Image

# -------------------------------
# Load CSV with better caching
# -------------------------------
csv_url = "https://raw.githubusercontent.com/pullanagari/Disease_app/main/data_temp.csv"

# Create directories if they don't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Function to load data with caching
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    df_main = pd.read_csv(csv_url)

    local_csv_path = "data/local_disease_data.csv"
    if os.path.exists(local_csv_path):
        df_local = pd.read_csv(local_csv_path)
        df_combined = pd.concat([df_main, df_local], ignore_index=True)
    else:
        df_combined = df_main

    df_combined["date"] = pd.to_datetime(df_combined["date"], errors="coerce", dayfirst=True)
    return df_combined

# Initialize session state
if "df" not in st.session_state:
    st.session_state.df = load_data()

def reload_data():
    st.session_state.df = load_data()

# -------------------------------
# Page Layout & Sidebar
# -------------------------------
st.set_page_config(
    page_title="South Australia Disease Surveillance",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide the top-right "View source" link, menu, and footer
hide_code = """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_code, unsafe_allow_html=True)

st.sidebar.markdown("## 🌾 South Australia Disease Surveillance")
menu = st.sidebar.radio("Navigation", ["Disease tracker", "Tag a disease", "About"])

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    reload_data()
    st.sidebar.success("Data refreshed!")

df = st.session_state.df

# -------------------------------
# Disease Tracker Page
# -------------------------------
if menu == "Disease tracker":
    st.markdown("## 🗺 Disease Tracker")

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
    mask = (
        (df["crop"] == crop)
        & (df["date"] >= pd.to_datetime(date_range[0]))
        & (df["date"] <= pd.to_datetime(date_range[1]))
    )
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

    # Map
    st.markdown("### Map View")
    m = folium.Map(location=[-36.76, 142.21], zoom_start=6)
    for _, row in df_filtered.iterrows():
        if not pd.isna(row["latitude"]) and not pd.isna(row["longitude"]):
            popup_text = f"{row.get('survey_location', 'Unknown')}"
            if not pd.isna(row.get("severity1_percent")):
                popup_text += f" | Severity1: {row['severity1_percent']}%"
            if not pd.isna(row.get("severity2_percent")):
                popup_text += f" | Severity2: {row['severity2_percent']}%"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=6,
                color="red",
                fill=True,
                fill_color="red",
                popup=popup_text,
            ).add_to(m)
    st_folium(m, width=800, height=450)

    # Graph
    st.markdown("### Disease Severity Graph")
    if not df_filtered.empty:
        fig = px.bar(
            df_filtered,
            x="survey_location",
            y="severity1_percent",
            title=f"{crop} - {disease if disease != 'All' else 'All diseases'}",
            labels={"severity1_percent": "Severity (%)"},
            color="severity1_percent",
            color_continuous_scale="reds",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for the graph.")

    # Table
    st.markdown("### Surveillance Summary")
    if not df_filtered.empty:
        st.dataframe(df_filtered[["date", "crop", "disease1", "survey_location", "severity1_percent"]])
        st.download_button(
            "Download CSV",
            df_filtered.to_csv(index=False).encode("utf-8"),
            "survey.csv",
            "text/csv",
        )
    else:
        st.info("No data available for the selected filters.")

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
            disease2 = st.selectbox("Disease 2", ["None"] + ["Stripe rust", "Leaf rust", "Blackleg"])
            severity1 = st.slider("Severity 1 (%)", 0, 100, 0)
            severity2 = st.slider("Severity 2 (%)", 0, 100, 0)
            latitude = st.number_input("Latitude", value=-36.76, step=0.01)
            longitude = st.number_input("Longitude", value=142.21, step=0.01)
        location = st.text_input("Location (Suburb)", "")
        field_type = st.text_input("Field Type", "")
        agronomist = st.text_input("Agronomist", "")
        plant_stage = st.selectbox(
            "Plant Growth Stage",
            ["Emergence", "Tillering", "Stem elongation", "Flowering", "Grain filling", "Maturity"],
        )

        uploaded_file = st.file_uploader("Attach Photo (Optional)", type=["png", "jpg", "jpeg"])

        submitted = st.form_submit_button("Submit")

        if submitted:
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
                "severity2_percent": severity2,
                "latitude": latitude,
                "longitude": longitude,
                "survey_location": location,
                "photo_filename": photo_filename if photo_filename else "",
            }

            new_df = pd.DataFrame([new_record])
            local_csv_path = "data/local_disease_data.csv"
            if os.path.exists(local_csv_path):
                new_df.to_csv(local_csv_path, mode="a", header=False, index=False)
            else:
                new_df.to_csv(local_csv_path, mode="w", header=True, index=False)

            st.cache_data.clear()
            reload_data()

            st.success("✅ Submission successful! Data saved to CSV.")

            if uploaded_file is not None:
                st.markdown("**Uploaded Photo Preview:**")
                image = Image.open(uploaded_file)
                st.image(image, caption="Disease Photo", use_column_width=True)

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
                key="download-csv",
            )
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
    """
    )


