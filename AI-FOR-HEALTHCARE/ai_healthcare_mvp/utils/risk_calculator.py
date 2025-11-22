# utils/risk_calculator.py

import math
import datetime

def ai_health_risk_score(steps, pain_level, medicine_taken, sleep_hours=None, mood=None):
    """
    AI Health Risk Score Model
    ----------------------------------
    • Pain level is the strongest indicator (55% weight)
    • Steps, medicine, sleep, and mood influence recovery but less heavily
    • Nonlinear scaling amplifies extreme cases
    """

    # ----------------------------------
    # 1️⃣ Normalize Steps
    # ----------------------------------
    if steps <= 1000:
        steps_score = 1.0
    elif steps <= 3000:
        steps_score = 0.8
    elif steps <= 6000:
        steps_score = 0.5
    elif steps <= 10000:
        steps_score = 0.3
    else:
        steps_score = 0.1

    # ----------------------------------
    # 2️⃣ Pain Level (Dominant Factor)
    # ----------------------------------
    pain_score = min(max(pain_level / 10.0, 0), 1.0)

    # ----------------------------------
    # 3️⃣ Medicine
    # ----------------------------------
    med_score = 0.35 if not medicine_taken else 0.05

    # ----------------------------------
    # 4️⃣ Sleep Quality
    # ----------------------------------
    if sleep_hours is None:
        sleep_score = 0.3
    elif sleep_hours < 5:
        sleep_score = 0.7
    elif sleep_hours < 7:
        sleep_score = 0.4
    else:
        sleep_score = 0.1

    # ----------------------------------
    # 5️⃣ Mood
    # ----------------------------------
    mood_score = 0.3
    if mood:
        mood = str(mood).lower()
        if mood in ["sad", "angry", "tired", "stressed"]:
            mood_score = 0.6
        elif mood in ["neutral"]:
            mood_score = 0.3
        elif mood in ["happy", "energetic", "relaxed"]:
            mood_score = 0.1

    # ----------------------------------
    # 6️⃣ Weighted Total Score
    # ----------------------------------
    total_score = (
        0.55 * pain_score +
        0.15 * steps_score +
        0.10 * med_score +
        0.10 * sleep_score +
        0.10 * mood_score
    )

    # ----------------------------------
    # 7️⃣ Nonlinear Risk Amplification
    # ----------------------------------
    risk_value = round((math.pow(total_score, 1.4)) * 100, 2)

    # ----------------------------------
    # 8️⃣ Categorize
    # ----------------------------------
    if risk_value >= 65:
        risk_level = "High"
        ai_recommendation = "⚠️ Severe pain or poor recovery indicators. Immediate medical attention recommended."
    elif risk_value >= 40:
        risk_level = "Moderate"
        ai_recommendation = "🟠 Monitor condition closely and ensure regular follow-ups."
    else:
        risk_level = "Low"
        ai_recommendation = "🟢 Patient is recovering well. Continue current care plan."

    return {
        "risk_score": risk_value,
        "risk_level": risk_level,
        "ai_recommendation": ai_recommendation,
        "evaluated_on": datetime.datetime.now().isoformat()
    }


# ------------------------------
# Manual Test (Optional)
# ------------------------------
if __name__ == "__main__":
    test_cases = [
        {"steps": 15000, "pain_level": 10, "medicine_taken": True, "sleep_hours": 8, "mood": "happy"},
        {"steps": 2000, "pain_level": 7, "medicine_taken": False, "sleep_hours": 5, "mood": "sad"},
        {"steps": 8000, "pain_level": 3, "medicine_taken": True, "sleep_hours": 7, "mood": "neutral"},
        {"steps": 12000, "pain_level": 1, "medicine_taken": True, "sleep_hours": 8, "mood": "relaxed"},
    ]

    for case in test_cases:
        print(f"\nInput: {case}")
        print("Result:", ai_health_risk_score(**case))
