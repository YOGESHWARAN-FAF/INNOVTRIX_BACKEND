import firebase_admin
from firebase_admin import db, messaging
from ..utils.logger import logger

def send_notification(uid, title, body):
    token = db.reference(f"users/{uid}/fcmToken").get()
    if not token:
        logger.error("No token found for user")
        return

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token
    )

    try:
        response = messaging.send(message)
        logger.info(f"Notification sent: {response}")
    except Exception as e:
        logger.error(f"Error sending FCM message: {e}")
