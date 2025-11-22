from firebase_config.firebase_connection import connect_to_firestore

# Try connecting to Firestore using environment-variable credentials
db = connect_to_firestore()

if db:
    try:
        test_ref = db.collection("test_data").document("connection_test")
        test_ref.set({"status": "success"})

        print("🔥 Test Firestore write successful!")
    except Exception as e:
        print("❌ Firestore write failed:", str(e))
else:
    print("❌ Firestore connection failed")
