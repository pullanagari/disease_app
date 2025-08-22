import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime

# -------------------------------
# Load CSV
# -------------------------------
csv_url = "https://raw.githubusercontent.com/pullanagari/Disease_app/main/data_temp.csv"
df = pd.read_csv(csv_url)

# Ensure proper datetime parsing
df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

# -------------------------------
# Sidebar Navigation
# -------------------------------
st.sidebar.title("Victoria Disease Surveillance")
menu = st.sidebar.radio("Navigation", ["Disease tracker", "Tag a disease", "About"])

# -------------------------------
# Disease Tracker Page
# -------------------------------
if menu == "Disease tracker":
    st.header("🗺 Disease Tracker")

    crop = st.selectbox("Choose a Crop", df["crop"].dropna().unique())
    disease = st.selectbox("Choose a Disease", ["All"] + sorted(df["disease1"].dropna().unique()))
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

    # Map
    st.subheader("Map View")
    m = folium.Map(location=[-36.76, 142.21], zoom_start=6)
    for _, row in df_filtered.iterrows():
        if not pd.isna(row["latitude"]) and not pd.isna(row["longitude"]):
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=6,
                color="red",
                fill=True,
                popup=f"{row['survey_location']} ({row['severity1_percent']}%)"
            ).add_to(m)
    st_data = st_folium(m, width=700, height=450)

    # Graph
    st.subheader("Disease Severity Graph")
    if not df_filtered.empty:
        fig = px.bar(df_filtered, x="survey_location", y="severity1_percent",
                     title=f"{crop} - {disease if disease != 'All' else 'All diseases'}",
                     labels={"severity1_percent": "Severity (%)"},
                     color="severity1_percent", color_continuous_scale="reds")
        st.plotly_chart(fig, use_container_width=True)

    # Table
    st.subheader("Surveillance Summary")
    st.dataframe(df_filtered[["date", "crop", "disease1", "survey_location", "severity1_percent"]])
    st.download_button(
        "Download CSV", df_filtered.to_csv(index=False).encode("utf-8"),
        "survey.csv", "text/csv"
    )

# -------------------------------
# Tag a Disease Page
# -------------------------------
elif menu == "Tag a disease":
    st.header("📌 Tag a Disease")

    with st.form("disease_form", clear_on_submit=True):
        date = st.date_input("Date", datetime.today())
        collector = st.selectbox("Collector Name", ["Hari Dadu", "Josh Fanning", "Other"])
        crop = st.selectbox("Crop", ["Wheat", "Barley", "Canola", "Lentil"])
        disease1 = st.selectbox("Disease 1", ["Stripe rust", "Leaf rust", "Blackleg"])
        severity1 = st.slider("Severity (%)", 0, 100, 0)
        latitude = st.number_input("Latitude", value=-36.76, step=0.01)
        longitude = st.number_input("Longitude", value=142.21, step=0.01)
        location = st.text_input("Location (Suburb)")
        submitted = st.form_submit_button("Submit")

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

            # Append new record to CSV
            new_df = pd.DataFrame([new_record])
            new_df.to_csv(csv_path, mode="a", header=False, index=False)

            st.success("✅ Submission successful! Data saved to CSV.")

# -------------------------------
# About Page
# -------------------------------
else:
    st.header("ℹ️ About Vic Ds App")
    st.write("""
    This application supports field crop pathology staff during surveillance activities to upload disease information 
    and visualize disease severity through maps, graphs, and tables.
    
    **Credits**  
    Developed by Hari Dadu (AgVic), Sam Rogers & Russell Edson (Uni of Adelaide),  
    supported by SAGIT internship program.
    """)


