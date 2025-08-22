import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime

# -------------------------------
# Custom Styling
# -------------------------------
st.markdown("""
<style>
    .main-header {
        font-size: 32px !important;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 30px;
    }
    .sub-header {
        font-size: 24px !important;
        font-weight: bold;
        color: #2ca02c;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    .metric-card {
        background-color: #f0f8ff;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        text-align: center;
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f1f1f1;
        color: #333;
        text-align: center;
        padding: 10px;
        font-size: 14px;
    }
    [data-testid="stSidebar"] {
        background-color: #e6f3ff;
    }
    .sidebar-title {
        color: #1f77b4;
        font-size: 24px;
        font-weight: bold;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Load CSV
# -------------------------------
csv_url = "https://raw.githubusercontent.com/pullanagari/Disease_app/main/data_temp.csv"
df = pd.read_csv(csv_url)

# Ensure proper datetime parsing
df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

# -------------------------------
# Page Layout & Sidebar
# -------------------------------
st.set_page_config(
    page_title="Victoria Disease Surveillance",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown('<p class="main-header">🌾 Victoria Disease Surveillance Dashboard</p>', unsafe_allow_html=True)

st.sidebar.markdown('<p class="sidebar-title">🌾 VicDS App</p>', unsafe_allow_html=True)
menu = st.sidebar.radio("Navigate", ["📊 Disease Tracker", "📌 Tag a Disease", "ℹ️ About"])

# Add logo or image in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Quick Stats")
st.sidebar.markdown(f"- **Total Records:** {len(df)}")
st.sidebar.markdown(f"- **Crops Tracked:** {df['crop'].nunique()}")
st.sidebar.markdown(f"- **Diseases Monitored:** {df['disease1'].nunique()}")

# -------------------------------
# Disease Tracker Page
# -------------------------------
if menu == "📊 Disease Tracker":
    st.markdown("## 🗺 Disease Surveillance Tracker")
    
    col1, col2, col3 = st.columns([1.5,1,1])
    
    with col1:
        crop = st.selectbox("🌾 Select Crop", df["crop"].dropna().unique(), key="crop_select")
    with col2:
        disease = st.selectbox("🦠 Select Disease", ["All"] + sorted(df["disease1"].dropna().unique()), key="disease_select")
    with col3:
        date_range = st.date_input("📅 Date Range", [datetime(2020,1,1), datetime.today()], key="date_range")

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
    st.markdown("### 📈 Key Surveillance Metrics")
    if not df_filtered.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("🔬 Total Surveys", len(df_filtered))
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("⚠️ Max Severity (%)", int(df_filtered["severity1_percent"].max()))
            st.markdown('</div>', unsafe_allow_html=True)
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("📊 Avg Severity (%)", round(df_filtered["severity1_percent"].mean(),1))
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("No data available for selected filters.")

    # Map
    st.markdown("### 🌍 Geographic Distribution")
    if not df_filtered.empty:
        m = folium.Map(location=[-36.76, 142.21], zoom_start=6)
        for _, row in df_filtered.iterrows():
            if not pd.isna(row["latitude"]) and not pd.isna(row["longitude"]):
                folium.CircleMarker(
                    location=[row["latitude"], row["longitude"]],
                    radius=6,
                    color="red",
                    fill=True,
                    fill_color="red",
                    popup=f"{row['survey_location']} ({row['severity1_percent']}%)"
                ).add_to(m)
        st_folium(m, width=800, height=450)
    else:
        st.info("No location data available for mapping.")
    
    # Severity Distribution
    st.markdown("### 📊 Severity Distribution")
    if not df_filtered.empty:
        severity_fig = px.histogram(df_filtered, x="severity1_percent", 
                                  title=f"{crop} - {disease if disease != 'All' else 'All diseases'} Severity Distribution",
                                  labels={"severity1_percent": "Severity (%)"},
                                  color_discrete_sequence=['#1f77b4'])
        st.plotly_chart(severity_fig, use_container_width=True)

    # Graph
    st.markdown("### 📈 Disease Severity by Location")
    if not df_filtered.empty:
        fig = px.bar(df_filtered, x="survey_location", y="severity1_percent",
                     title=f"{crop} - {disease if disease != 'All' else 'All diseases'} Severity Report",
                     labels={"severity1_percent": "Severity (%)", "survey_location": "Location"},
                     color="severity1_percent", color_continuous_scale="reds")
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data to display for selected filters.")

    # Table
    st.markdown("### 📋 Surveillance Summary")
    if not df_filtered.empty:
        st.dataframe(df_filtered[["date", "crop", "disease1", "survey_location", "severity1_percent"]].sort_values("date", ascending=False))
        st.download_button(
            "💾 Download Filtered Data", df_filtered.to_csv(index=False).encode("utf-8"),
            f"{crop}_{disease}_survey.csv", "text/csv"
        )
    else:
        st.info("No records match your selected criteria.")

# -------------------------------
# Tag a Disease Page
# -------------------------------
elif menu == "📌 Tag a Disease":
    st.markdown("## 📌 Tag a New Disease Report")
    
    with st.form("disease_form", clear_on_submit=True):
        st.markdown("### 🧾 Report Details")
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("📅 Survey Date", datetime.today())
            collector = st.selectbox("👤 Collector Name", ["Hari Dadu", "Josh Fanning", "Other"], key="collector")
            crop = st.selectbox("🌾 Crop Type", ["Wheat", "Barley", "Canola", "Lentil"], key="crop")
        with col2:
            disease1 = st.selectbox("🦠 Disease Type", ["Stripe rust", "Leaf rust", "Blackleg"], key="disease")
            severity1 = st.slider("📊 Severity (%)", 0, 100, 0)
            latitude = st.number_input("📍 Latitude", value=-36.76, step=0.01, format="%.6f")
            longitude = st.number_input("📍 Longitude", value=142.21, step=0.01, format="%.6f")
        
        location = st.text_input("🗺 Survey Location (Suburb/City)")
        
        submitted = st.form_submit_button("📤 Submit Disease Report")

        if submitted:
            new_record = {
                "date": date.strftime("%d/%m/%Y"),
                "collector_name": collector,
                "crop": crop,
                "disease1": disease1,
                "severity1_percent": severity1,
                "latitude": latitude,
                "longitude": longitude,
                "survey_location": location
            }

            # Display submitted information
            st.success("✅ Disease report submitted successfully!")
            st.balloons()
            st.markdown("### Submitted Information:")
            st.json(new_record)
            
            # In a real app, you would save this to a database
            # For this example, we'll just show the process
            st.info("In a deployed application, this data would be saved to the surveillance database.")

# -------------------------------
# About Page
# -------------------------------
else:
    st.markdown("## ℹ️ About Victoria Disease Surveillance App")
    st.markdown("""
    ### 🎯 Purpose
    This application supports field crop pathology staff during surveillance activities by providing:
    - Easy data entry for disease observations
    - Interactive visualizations of disease severity
    - Geographic mapping of disease occurrences
    - Real-time data analysis for decision making
    
    ### 🔬 Features
    - **📊 Disease Tracker**: Interactive dashboard showing disease surveillance data with customizable filters
    - **📌 Tag a Disease**: Simple form for recording new disease observations
    - **🗺 Geographic Visualization**: Interactive map showing disease locations and severity
    - **📈 Data Analysis**: Charts and graphs for understanding disease patterns
    - **💾 Export Functionality**: Download filtered data for further analysis
    
    ### 👥 Target Users
    - Field crop pathologists
    - Agricultural extension officers
    - Research scientists
    - Farm advisors
    
    ### 📞 Contact
    For questions about this application, please contact the Department of Primary Industries.
    """)

# Footer
st.markdown('<div class="footer">Victoria Disease Surveillance App | Department of Primary Industries | Last Updated: 2023</div>', unsafe_allow_html=True)
