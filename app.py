import streamlit as st
import leafmap.foliumap as leafmap

st.set_page_config(page_title="GIS App", layout="wide")

st.title("🌍 GIS App with Streamlit + Leafmap")

# Sidebar inputs
dataset = st.sidebar.selectbox(
    "Select a basemap:",
    ["OpenStreetMap", "Esri.WorldImagery", "CartoDB.DarkMatter"]
)

# # Create map
m = leafmap.Map(center=[-34.92, 138.6], zoom=6, basemap=dataset)

# # Optional: load vector/raster
# # Example with GeoJSON
geojson = "https://raw.githubusercontent.com/giswqs/leafmap/master/examples/data/countries.geojson"
m.add_geojson(geojson, layer_name="Countries")

# # Example with raster (keep small for cloud)
# # tif = "https://github.com/giswqs/data/raw/main/raster/srtm90.tif"
# # m.add_raster(tif, layer_name="Elevation")

# # Display map
m.to_streamlit(height=600)
