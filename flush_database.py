import os
import streamlit as st
import pandas as pd

# 1️⃣ Clear the CSV database
local_path = "data/local_disease_data.csv"
if os.path.exists(local_path):
    os.remove(local_path)
    print("✅ Local disease database removed.")

# 2️⃣ Clear Streamlit cache
st.cache_data.clear()
print("✅ Streamlit cache cleared.")

# 3️⃣ Clear session state (optional if run outside Streamlit)
if "st" in globals():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    print("✅ Streamlit session state cleared.")

# 4️⃣ Recreate empty CSV with proper columns
columns = ["date", "collector_name", "field_type", "Agronomist", "crop", "variety",
           "plant_stage", "disease1", "disease2", "disease3",
           "severity1_percent", "severity2_percent", "severity3_percent",
           "latitude", "longitude", "survey_location", "photo_filename",
           "field_notes", "sample_taken", "molecular_diagnosis"]

pd.DataFrame(columns=columns).to_csv(local_path, index=False)
print("✅ Empty CSV created.")
