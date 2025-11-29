import os
import firebase_admin
from firebase_admin import credentials
from .utils.logger import logger

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    db_url = os.getenv("DATABASE_URL")

    if not cred_path or not db_url:
        logger.critical("Missing Firebase credentials or Database URL in environment variables.")
        raise ValueError("Missing Firebase configuration.")

    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {"databaseURL": db_url})
            logger.info("Firebase initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize Firebase: {e}")
            raise e
