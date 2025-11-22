import streamlit as st
import pandas as pd
import os
import sys
import math
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()  # loads .env file


# Add parent directory to path so firebase_config can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# -------------------------------------------------------------
#                FIREBASE INITIALIZATION (SAFE)
# -------------------------------------------------------------
from firebase_config.firebase_connection import connect_to_firestore

db = connect_to_firestore()
if not db:
    st.error("❌ Failed to connect to Firebase. Check environment variables.")
    st.stop()

# -------------------------------------------------------------
#                    AI RISK SCORE
# -------------------------------------------------------------
def ai_health_risk_score(steps, pain_level, medicine_taken, sleep_hours=None, mood=None):
    pain_score = min(max(pain_level / 10.0, 0), 1.0)
    steps_score = 0.1 if steps > 10000 else (0.3 if steps > 6000 else (0.5 if steps > 3000 else 0.9))
    med_score = 0.05 if medicine_taken else 0.35
    sleep_score = 0.1 if (sleep_hours or 0) >= 7 else (0.4 if (sleep_hours or 0) >= 5 else 0.7)
    mood_score = 0.1 if mood and str(mood).lower() in ["happy", "energetic", "relaxed"] else \
                 (0.6 if mood and str(mood).lower() in ["sad", "tired", "stressed"] else 0.3)

    total = 0.55 * pain_score + 0.15 * steps_score + 0.10 * med_score + 0.10 * sleep_score + 0.10 * mood_score
    risk = round((math.pow(total, 1.4)) * 100, 2)

    if risk >= 65:
        return {"risk_score": risk, "risk_level": "High", "ai_recommendation": "Immediate consultation advised."}
    elif risk >= 40:
        return {"risk_score": risk, "risk_level": "Moderate", "ai_recommendation": "Monitor closely."}
    return {"risk_score": risk, "risk_level": "Low", "ai_recommendation": "Maintain routine."}

# -------------------------------------------------------------
#                       FETCH DOCTORS
# -------------------------------------------------------------
@st.cache_data(ttl=10)
def fetch_doctors():
    docs = db.collection("doctors").stream()
    out = {}
    for d in docs:
        data = d.to_dict()
        out[data["name"]] = data.get("password", "1234")
    return out

# -------------------------------------------------------------
#                  FETCH PATIENT DATA
# -------------------------------------------------------------
@st.cache_data(ttl=5)
def fetch_patients():
    docs = db.collection("patients").stream()
    out = []
    for d in docs:
        data = d.to_dict()
        data["_doc_id"] = d.id
        data["timestamp_parsed"] = pd.to_datetime(data.get("timestamp"), errors="coerce")
        out.append(data)
    return out

# -------------------------------------------------------------
#      CLEAN MAPPING OF OLD DOCTOR IDS → NEW NAMES
# -------------------------------------------------------------
DOCTOR_NAME_MAPPING = {
    "doctor_01": "Dr. Evelyn Reed",
    "doctor_0001": "Dr. Evelyn Reed",
    "doctor_02": "Dr. Marcus Chen",
    "doctor_06": "Dr. Omar Khan",
}

def normalize_doctor_name(raw_name):
    return DOCTOR_NAME_MAPPING.get(raw_name, raw_name)

# -------------------------------------------------------------
#                     STREAMLIT UI
# -------------------------------------------------------------
st.set_page_config(page_title="Doctor Dashboard", layout="wide")
st.markdown("<h1>Doctor Dashboard</h1>", unsafe_allow_html=True)

# -------------------------------------------------------------
#                   DOCTOR LOGIN PAGE
# -------------------------------------------------------------
doctors = fetch_doctors()
doctor_names = ["Select Doctor"] + list(doctors.keys())

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    selected = st.selectbox("Select your name:", doctor_names)
    if selected != "Select Doctor":
        password_input = st.text_input("Enter Password:", type="password")
        if st.button("Login"):
            if password_input == doctors[selected]:
                st.session_state.logged_in = True
                st.session_state.doctor_name = selected
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("❌ Incorrect password")
    st.stop()

# -------------------------------------------------------------
#       AFTER LOGIN: SHOW PATIENTS FOR THIS DOCTOR
# -------------------------------------------------------------
current_doctor = st.session_state.doctor_name
st.markdown(f"Logged in as: **{current_doctor}**")

patients_raw = fetch_patients()
processed_patients = []
for p in patients_raw:
    p["assigned_doctor"] = normalize_doctor_name(p.get("assigned_doctor", "Unassigned"))
    processed_patients.append(p)

df = pd.DataFrame(processed_patients)
df = df[df["assigned_doctor"] == current_doctor]

if df.empty:
    st.warning(f"No patients assigned yet for {current_doctor}.")
    st.stop()

# Compute AI risk scores and sort
final_rows = []
for _, r in df.iterrows():
    score = ai_health_risk_score(
        steps=int(r.get("steps_walked", 0)),
        pain_level=int(r.get("pain_level", 5)),
        medicine_taken=str(r.get("medicine_taken", "no")).lower() == "yes",
        sleep_hours=float(r.get("sleep_hours", 0)),
        mood=r.get("mood")
    )
    r = r.to_dict()
    r.update(score)
    final_rows.append(r)

df_final = pd.DataFrame(final_rows)
df_final = df_final.sort_values(by=["risk_score", "timestamp_parsed"], ascending=[False, True])

# -------------------------------------------------------------
#                   SHOW PATIENT CARDS
# -------------------------------------------------------------
for _, row in df_final.iterrows():
    border = "8px solid #4caf50"
    if row["risk_level"] == "High":
        border = "8px solid #ff4d4d"
    elif row["risk_level"] == "Moderate":
        border = "8px solid #ffa31a"

    st.markdown(
        f"""
        <div style="
            background:white; 
            padding:18px; 
            margin-bottom:16px;
            border-left:{border};
            border-radius:10px;">
        """,
        unsafe_allow_html=True
    )

    st.markdown(f"**{row['name']}** — *{row['timestamp']}*")
    st.write(f"Pain — {row['pain_level']}   •   **Steps:** {row['steps_walked']}   •  **Medicine:** {row['medicine_taken']}")
    st.write(f"AI Risk — {row['risk_level']} ({row['risk_score']})")
    st.info(f"AI Recommendation — {row['ai_recommendation']}")
    st.write("Patient Notes —")
    st.write(row.get("notes", ""))

    # Doctor Notes Editing
    new_notes = st.text_area(
        "Doctor Notes:",
        value=row.get("doctor_notes", ""),
        key=f"note_{row['_doc_id']}",
        height=100
    )

    if st.button("Save Notes", key=f"save_{row['_doc_id']}"):
        db.collection("patients").document(row["_doc_id"]).update({"doctor_notes": new_notes})
        st.success("Saved!")

    st.markdown("</div>", unsafe_allow_html=True)
