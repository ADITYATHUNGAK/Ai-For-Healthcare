import streamlit as st
import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pandas as pd
import math
import sys

# --- Gemini Imports and Configuration ---
from google import genai
from google.genai.errors import APIError

# Initialize Gemini Client
client = None
try:
    # Use os.getenv to check for the key's presence before creating the client
    if not os.getenv("GEMINI_API_KEY"):
        # This will trigger the st.error below if the key is not set
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
    client = genai.Client()
except Exception as e:
    # The error message will appear above the main content if the key is missing
    st.error(f"Gemini API key error: {e}. Please set the GEMINI_API_KEY environment variable if you want to use the Chatbot.")

# Model to use for the chat
GEMINI_MODEL = 'gemini-2.5-flash'

# System Instruction to define the chatbot's persona and rules
SYSTEM_INSTRUCTION = (
    "You are a friendly, non-diagnostic AI Patient Health Assistant. "
    "Your primary role is to provide information, reminders, and educational content to the patient. "
    "Follow these strict rules:\n"
    "1. Never provide a medical diagnosis or treatment advice.\n"
    "2. Always preface medical suggestions with a strong disclaimer to consult a doctor (e.g., 'Please consult your primary care physician...').\n"
    "3. Be encouraging and supportive.\n"
    "4. Keep answers concise and relevant to patient management."
)
# ----------------------------------------


# Optional: import your risk calculator (fallback if missing)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from utils.risk_calculator import ai_health_risk_score
except Exception:
    def ai_health_risk_score(steps, pain_level, medicine_taken, sleep_hours=None, mood=None):
        pain_score = min(max(pain_level / 10.0, 0), 1.0)
        steps_score = 0.1 if steps > 10000 else (0.3 if steps > 6000 else (0.5 if steps > 3000 else 0.9))
        med_score = 0.05 if medicine_taken else 0.35
        sleep_score = 0.1 if (sleep_hours or 0) >= 7 else (0.4 if (sleep_hours or 0) >= 5 else 0.7)
        mood_score = 0.1 if mood and str(mood).lower() in ["happy", "energetic", "relaxed"] else \
                            (0.6 if mood and str(mood).lower() in ["sad", "tired", "stressed"] else 0.3)
        total = 0.55*pain_score + 0.15*steps_score + 0.10*med_score + 0.10*sleep_score + 0.10*mood_score
        risk = round((math.pow(total, 1.4)) * 100, 2)
        if risk >= 65:
            level = "High"; rec = "Immediate consultation advised."
        elif risk >= 40:
            level = "Moderate"; rec = "Monitor closely."
        else:
            level = "Low"; rec = "Maintain routine."
        return {"risk_score": risk, "risk_level": level, "ai_recommendation": rec}


# ✔ Default doctor assignment per department (UPDATED TO USE FULL NAMES AND IDs)
DEPARTMENT_DOCTORS = {
    "Orthopedics": "Dr. Evelyn Reed",
    "Cardiology": "Dr. Marcus Chen",
    "Neurology": "Dr. Sarah Jones",
    "General Medicine": "Dr. Alex Thompson",
    "Dermatology": "Dr. Chloe Davis",
    "ENT": "Dr. Omar Khan",
    "Gastroenterology": "Dr. Lena Rodriguez",
    "Physiotherapy": "Dr. Ben Carter"
}


# Firebase init (Using local file path as requested)
*******************************************
****************:
    st.error("Firebase key not found: " + cred_path)
    # st.stop() # Commenting out stop to allow the rest of the UI to load
    db = None
else:
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    db = firestore.client()


# Page config & CSS (supreme patient UI)
st.set_page_config(page_title="Patient Dashboard",  layout="centered")
st.markdown("""
<style>
body { background: linear-gradient(180deg,#f8fbff,#eef6ff); font-family: 'Segoe UI', sans-serif; }
.header { text-align:center; margin-bottom:12px; }
.h1 { color:#004aad; font-size:28px; font-weight:800; }
.card { background:rgba(255,255,255,0.85); padding:18px; border-radius:14px; box-shadow:0 12px 30px rgba(6,30,60,0.06); }
.small { color:#6b7a99; font-size:13px; }
.note { background:#f6f9ff; padding:10px; border-radius:10px; border:1px solid rgba(3,53,128,0.03); }
.stChat {
    max-height: 400px; /* Constrain the height of the chat window */
    overflow-y: auto;
    border-radius: 10px;
    border: 1px solid #eef6ff;
    padding: 10px;
    margin-top: 20px;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="header"><div class="h1">Patient Portal</div>'
    '<div class="small">Submit your daily recovery report</div></div>',
    unsafe_allow_html=True
)


# --- CHATBOT LOGIC (Re-integrated from previous version) ---
def patient_chatbot():
    """Implements the core chatbot interface and logic for the Patient Dashboard."""
    st.markdown("---")
    st.subheader("Health Assistant Chatbot")
    st.markdown("Ask general questions about your health, but remember I cannot diagnose.")

    # Check if client is initialized
    if not client:
        st.warning("Chatbot functionality is disabled because the Gemini API key is missing.")
        return

    # Initialize chat history in session state
    if "messages" not in st.session_state:
        # FIX: Change role from "assistant" to "model" to comply with Gemini API
        st.session_state.messages = [
            {"role": "model", "content": "Hello! I am your AI Health Assistant. How can I help you manage your health today? Remember, I cannot provide diagnoses."}
        ]
    
    # Use a container for the chat history to limit its height
    with st.container(height=350, border=True):
        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            # Streamlit UI supports "assistant" for the chatbot display
            display_role = "assistant" if message["role"] == "model" else message["role"]
            with st.chat_message(display_role):
                st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Ask a question about your health...", key="chatbot_input"):
        # Add user message to chat history using the API's expected role "user"
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message in chat container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate the assistant response
        try:
            # Prepare conversation for the API call
            # This mapping converts Streamlit's stored history roles ('user', 'model')
            # to the format expected by the API.
            contents = [
                {"role": msg["role"], "parts": [{"text": msg["content"]}]}
                for msg in st.session_state.messages
            ]

            # Use a configuration object to pass the system instruction
            config = genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION
            )

            with st.chat_message("assistant"):
                # Placeholder for streaming or just showing a thinking indicator
                with st.spinner("Assistant is thinking..."):
                    # Call the Gemini API with the system instruction config
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=contents,
                        config=config # Pass the new configuration
                    )
                    
                    assistant_response = response.text

                st.markdown(assistant_response)
            
            # Add assistant response to chat history using the API's expected role "model"
            st.session_state.messages.append({"role": "model", "content": assistant_response})

        except APIError as e:
            st.error(f"An API Error occurred: {e}. Check the console for details.")
            st.session_state.messages.pop() # Remove the user's last message if the API call fails
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            st.session_state.messages.pop() # Remove the user's last message if the API call fails
# -----------------------------------------------------------


# Layout
with st.container():
    col1, col2 = st.columns([2, 1])

    # ---------------- PATIENT FORM ----------------
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        name = st.text_input("Full name", key="p_name")

        # ✔ Department Selection
        department = st.selectbox(
            "Department",
            list(DEPARTMENT_DOCTORS.keys()),
            key="p_dept"
        )

        # ✔ Auto-assigned Doctor (doctor ID)
        assigned_doctor = DEPARTMENT_DOCTORS.get(department, "not_assigned")
        st.markdown(f"Assigned Doctor-{assigned_doctor}") # Changed text from 'Assigned Doctor ID'

        pain = st.slider("Pain level (0–10)", 0, 10, 5, key="p_pain")
        steps = st.number_input("Steps walked today", min_value=0, value=0, key="p_steps")
        medicine = st.selectbox("Medicine taken today?", ["Yes", "No"], key="p_med")
        sleep_hours = st.number_input("Sleep hours (last 24h)", min_value=0.0, max_value=24.0, step=0.5, value=7.0, key="p_sleep")
        mood = st.selectbox("Mood", ["Neutral", "Happy", "Sad", "Tired", "Stressed"], key="p_mood")
        notes = st.text_area("Any notes for your doctor", key="p_notes", height=140)

        st.markdown("</div>", unsafe_allow_html=True)

        # SAVE to Firebase (ROOT ONLY)
        if st.button("Submit Report", use_container_width=True):
            if db is None:
                st.error("Cannot submit: Firebase is not initialized. Please check the `serviceAccountKey.json` path.")
            elif not name.strip():
                st.error("Please enter your full name.")
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Using a timestamp in the doc ID to ensure uniqueness
                doc_id = f"{name.strip().replace(' ', '_').lower()}_{datetime.now().timestamp()}"

                payload = {
                    "name": name.strip(),
                    "department": department,
                    "assigned_doctor": assigned_doctor, # Stores the full name and ID string
                    "pain_level": int(pain),
                    "steps_walked": int(steps),
                    "medicine_taken": medicine,
                    "sleep_hours": float(sleep_hours),
                    "mood": mood,
                    "notes": notes,
                    "doctor_notes": "",
                    "ai_risk_score": None, # Will be computed below
                    "ai_recommendation": "",
                    "timestamp": timestamp
                }

                # Compute AI Score immediately upon submission
                ai = ai_health_risk_score(
                    steps=int(steps),
                    pain_level=int(pain),
                    medicine_taken=str(medicine).strip().lower() == "yes",
                    sleep_hours=float(sleep_hours),
                    mood=mood
                )
                payload["ai_risk_score"] = ai['risk_score']
                payload["ai_recommendation"] = ai['ai_recommendation']

                try:
                    # Using the 'patients' collection as per your original code
                    db.collection("patients").document(doc_id).set(payload)
                    st.success("Submitted")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error writing to Firebase: {e}")


    # ---------------- DOCTOR PRESCRIPTION VIEW ----------------
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("Latest Doctor Prescription")

        lookup_name = st.text_input("Enter your name to view latest prescription", key="lookup_name")

        if st.button("View Latest"):
            if db is None:
                st.error("Cannot view: Firebase is not initialized.")
            elif not lookup_name.strip():
                st.error("Enter your name.")
            else:
                try:
                    docs = db.collection("patients").where("name", "==", lookup_name.strip()).stream()
                    latest = None
                    
                    # Manual sorting by timestamp string to find the latest
                    all_data = []
                    for d in docs:
                        all_data.append(d.to_dict())

                    if all_data:
                        all_data.sort(key=lambda x: x.get('timestamp', '1900-01-01'), reverse=True)
                        latest = all_data[0]


                    if latest and latest.get("doctor_notes"):
                        st.markdown(f"**Prescription (on {latest.get('timestamp', ''):.16s}):**")
                        st.markdown(f"<div class='note'>{latest.get('doctor_notes')}</div>", unsafe_allow_html=True)
                    else:
                        st.info("No prescription found yet.")

                except Exception as e:
                    st.error(f"Error reading from Firebase: {e}")

        st.markdown("</div>", unsafe_allow_html=True)

# ---------------- AI SUMMARY (Check) ----------------
if st.button("Check My Latest AI Summary", key="ai_summary_check"):
    if db is None:
        st.error("Cannot check AI Summary: Firebase is not initialized.")
    elif not lookup_name.strip():
        st.error("Enter your name in the Prescription lookup section above.")
    else:
        try:
            docs = db.collection("patients").where("name", "==", lookup_name.strip()).stream()
            latest = None
            
            # Manual sorting by timestamp string to find the latest
            all_data = []
            for d in docs:
                all_data.append(d.to_dict())

            if all_data:
                all_data.sort(key=lambda x: x.get('timestamp', '1900-01-01'), reverse=True)
                latest = all_data[0]

            if not latest:
                st.warning("No record found for that name.")
            else:
                # Use the pre-computed scores if available, otherwise compute now
                risk_score = latest.get("ai_risk_score")
                recommendation = latest.get("ai_recommendation")
                risk_level = "Unknown"
                
                if risk_score is None:
                    # Fallback computation (shouldn't be needed if submission worked)
                    steps = int(latest.get("steps_walked", 0))
                    pain = int(latest.get("pain_level", 5))
                    med = str(latest.get("medicine_taken","No")).strip().lower() == "yes"
                    sleep = float(latest.get("sleep_hours", 0))
                    mood = latest.get("mood", None)
                    ai = ai_health_risk_score(steps=steps, pain_level=pain, medicine_taken=med, sleep_hours=sleep, mood=mood)
                    risk_score = ai['risk_score']
                    recommendation = ai['ai_recommendation']
                    risk_level = ai['risk_level']
                elif risk_score >= 65:
                    risk_level = "High"
                elif risk_score >= 40:
                    risk_level = "Moderate"
                else:
                    risk_level = "Low"


                st.markdown(f"AI Risk-{risk_level}-Score-{risk_score}**")
                st.markdown(f"Recommendation-{recommendation}")

        except Exception as e:
            # CORRECTED SYNTAX ERROR HERE (sterror -> st.error)
            st.error(f"Error computing AI: {e}") 

# --- Chatbot Display ---

patient_chatbot()
