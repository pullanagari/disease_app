import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import os
from PIL import Image

# Load custom CSS
def load_css():
    with open("styles.css") as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

load_css()

# -------------------------------
# Loading
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

# Create custom header
st.markdown("""
<div class="header">
    <div class="header-content">
        <div class="logo">
            <i class="fas fa-seedling"></i>
            <h1>South Australia Disease Surveillance</h1>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Load Font Awesome for icons
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">', unsafe_allow_html=True)

# Create navigation tabs
menu_options = ["Disease tracker", "Tag a disease", "About"]
menu = st.radio("Navigation", menu_options, label_visibility="collapsed", horizontal=True)

# Style the radio buttons as tabs
st.markdown("""
<style>
    .stRadio > div {
        display: flex;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 50px;
        padding: 5px;
        margin-bottom: 20px;
    }
    .stRadio > div > label {
        padding: 10px 20px;
        border-radius: 50px;
        transition: all 0.3s ease;
        font-weight: 500;
        margin-right: 5px;
    }
    .stRadio > div > label:last-child {
        margin-right: 0;
    }
    .stRadio > div > label[data-testid="stRadioLabel"] > div:first-child {
        background: transparent !important;
    }
    .stRadio > div > label[data-testid="stRadioLabel"] {
        background: transparent;
        color: #2c3e50 !important;
    }
    .stRadio > div > label[data-testid="stRadioLabel"]:hover {
        background: rgba(52, 152, 219, 0.1) !important;
    }
    .stRadio > div > label[data-testid="stRadioLabel"] > div:first-child {
        background: transparent !important;
    }
    div[role="radiogroup"] > label[data-testid="stRadioLabel"]:has(input:checked) {
        background: #1abc9c !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# Refresh button
if st.button("🔄 Refresh Data", key="refresh_button"):
    reload_data()
    st.success("Data refreshed!")

df = st.session_state.df

# -------------------------------
# Disease Tracker Page

if menu == "Disease tracker":
    st.markdown("""
    <div class="main-content">
        <div class="sidebar">
            <h2 class="sidebar-title"><i class="fas fa-filter"></i> Data Filters</h2>
    """, unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1.5, 1, 1])

        with col1:
            crop = st.selectbox("Choose a Crop", ["All"] + sorted(df["crop"].dropna().unique()))
        with col2:
            disease = st.selectbox("Choose a Disease", ["All"] + sorted(df["disease1"].dropna().unique()))
        with col3:
            min_date = df["date"].min().date() if not df["date"].isna().all() else datetime(2020, 1, 1).date()
            max_date = df["date"].max().date() if not df["date"].isna().all() else datetime.today().date()
            date_range = st.date_input("Select Date Range", [min_date, max_date])
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("""
        <div class="dashboard">
    """, unsafe_allow_html=True)

    # Filter data
    mask = (
        (df["date"] >= pd.to_datetime(date_range[0]))
        & (df["date"] <= pd.to_datetime(date_range[1]))
    )
    if crop != "All":
        mask &= df["crop"] == crop
    if disease != "All":
        mask &= df["disease1"] == disease

    df_filtered = df.loc[mask]

    # Metrics
    st.markdown("""
    <div class="metrics">
        <div class="metric-card">
            <div class="metric-title">Total Surveys</div>
            <div class="metric-value">""" + str(len(df_filtered)) + """</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Max Severity</div>
            <div class="metric-value">""" + (str(int(df_filtered["severity1_percent"].max())) + "%" if not df_filtered.empty else "0%") + """</div>
        </div>
        <div class="metric-card">
            <div class="metric-title">Avg. Severity</div>
            <div class="metric-value">""" + (str(round(df_filtered["severity1_percent"].mean(), 1)) + "%" if not df_filtered.empty else "0%") + """</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Map
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Map View</h2>
    """, unsafe_allow_html=True)
    
    # Add legend for diseases
    unique_diseases = df["disease1"].dropna().unique()
    disease_colors = px.colors.qualitative.Set3[:len(unique_diseases)]
    disease_color_map = dict(zip(unique_diseases, disease_colors))
    
    legend_html = ""
    for dis, col in disease_color_map.items():
        legend_html += f'<div class="legend-item"><div class="legend-color" style="background:{col};"></div><span>{dis}</span></div>'
    
    st.markdown(f'<div class="legend">{legend_html}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Crop symbols
    crop_symbols = {
        "Wheat": "🌾",      
        "Rice": "🍚",       
        "Corn": "🌽",       
        "Barley": "🍺", 
        "Oats": "🌾🌾"
    }
    
    crop_symbols_html = ""
    for crop_name, symbol in crop_symbols.items():
        crop_symbols_html += f'<div class="crop-item">{symbol} {crop_name}</div>'
    
    st.markdown(f'<div class="crop-symbols">{crop_symbols_html}</div>', unsafe_allow_html=True)

    # Create map
    m = folium.Map(location=[-36.76, 142.21], zoom_start=6)

    for _, row in df_filtered.iterrows():
        if not pd.isna(row["latitude"]) and not pd.isna(row["longitude"]):
            popup_text = f"{row.get('survey_location', 'Unknown')}"
            if not pd.isna(row.get("severity1_percent")):
                popup_text += f" | Severity1: {row['severity1_percent']}%"
            if not pd.isna(row.get("severity2_percent")):
                popup_text += f" | Severity2: {row['severity2_percent']}%"

            color = disease_color_map.get(row["disease1"], "gray")

            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                popup=popup_text,
            ).add_to(m)

    # Add legend manually for diseases
    legend_html = """
     <div style="position: fixed; 
     bottom: 50px; left: 50px; width: 200px; height: auto; 
     background-color: white; border:2px solid grey; z-index:9999; font-size:14px;
     padding: 10px;">
     <b>Disease Legend</b><br>
    """
    for dis, col in disease_color_map.items():
        legend_html += f'<i style="background:{col};width:15px;height:15px;display:inline-block;margin-right:5px;"></i>{dis}<br>'
    legend_html += "</div>"

    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, width=800, height=450)
    st.markdown("</div>", unsafe_allow_html=True)

    # Graph
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Disease Severity Graph</h2>
        </div>
    """, unsafe_allow_html=True)
    
    if not df_filtered.empty:
        fig = px.bar(
            df_filtered,
            x="survey_location",
            y="severity1_percent",
            title=f"{crop} - {disease if disease != 'All' else 'All diseases'}",
            labels={"severity1_percent": "Severity (%)"},
            color="disease1",
            color_discrete_map=disease_color_map,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for the graph.")
    
    st.markdown("</div>", unsafe_allow_html=True)

    # Table
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Surveillance Summary</h2>
        </div>
    """, unsafe_allow_html=True)
    
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
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# -------------------------------
# Tag a Disease Page

elif menu == "Tag a disease":
    st.markdown("""
    <div class="main-content">
        <div class="dashboard">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Tag a Disease</h2>
                </div>
    """, unsafe_allow_html=True)
    
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

    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Export Data</h2>
        </div>
    """, unsafe_allow_html=True)
    
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
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# -------------------------------
# About Page
# -------------------------------
else:
    st.markdown("""
    <div class="main-content">
        <div class="dashboard">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">About SA Ds App</h2>
                </div>
    """, unsafe_allow_html=True)
    
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
    
    st.markdown("</div></div></div>", unsafe_allow_html=True)

# Add footer
st.markdown("""
<div class="footer">
    <p>© 2023 South Australia Disease Surveillance System | Department of Primary Industries and Regions</p>
</div>
""", unsafe_allow_html=True)
