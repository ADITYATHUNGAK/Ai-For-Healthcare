import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import tempfile

firebase_app = None

def connect_to_firestore():
    """
    Safely initializes Firebase using environment variables.
    Creates a temporary JSON file for the credentials.
    """
    global firebase_app

    try:
        if firebase_admin._apps:
            return firestore.client()

        # Build credentials dictionary
        firebase_creds = {
            "type": os.getenv("FIREBASE_TYPE"),
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
            "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
        }

        # Write temporary JSON file
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as temp_file:
            json.dump(firebase_creds, temp_file)
            temp_file_path = temp_file.name

        # Initialize Firebase
        cred = credentials.Certificate(temp_file_path)
        firebase_admin.initialize_app(cred)

        print("🔥 Firebase initialized using environment variables")

        return firestore.client()

    except Exception as e:
        print("❌ Firebase connection error:", str(e))
        return None
