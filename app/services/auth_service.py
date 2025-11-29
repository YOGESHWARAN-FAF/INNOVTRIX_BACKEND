import os
import re
import json
import time
import requests
from http.client import RemoteDisconnected
from requests.exceptions import SSLError
from firebase_admin import auth, db
from ..utils.logger import logger
from ..utils.error_handler import AppError

class AuthService:
    
    _INVALID_DB_CHARS = {'.', '#', '$', '[', ']', '/'}
    API_KEY = os.getenv("FIREBASE_API_KEY")

    TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'access_tokens.json')

    @staticmethod
    def _load_tokens():
        try:
            if os.path.exists(AuthService.TOKEN_FILE):
                with open(AuthService.TOKEN_FILE, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
            return []

    @staticmethod
    def _save_tokens(tokens):
        try:
            with open(AuthService.TOKEN_FILE, 'w') as f:
                json.dump(tokens, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
            return False

    @staticmethod
    def get_valid_keys():
        return AuthService._load_tokens()

    @staticmethod
    def update_valid_keys(keys):
        if AuthService._save_tokens(keys):
            return keys
        raise AppError("Failed to save tokens", 500)

    @staticmethod
    def _is_valid_db_key(value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        v = value.strip()
        if v == "":
            return False
        return not any(c in v for c in AuthService._INVALID_DB_CHARS)

    @staticmethod
    def normalize_state(value):
        if not value:
            return None
        v = value.lower().strip()
        if v in ["on", "off"]:
            return v
        if v.isdigit() and 1 <= int(v) <= 5:
            return v
        return None

    @staticmethod
    def verify_token(token):
        if not token:
            raise AppError("Missing token", 401)
        # Try a few times for transient network/SSL issues seen in some environments
        token = token.replace("Bearer ", "")
        last_exc = None
        for attempt in range(1, 4):
            try:
                decoded = auth.verify_id_token(token)
                return decoded.get("uid")
            except Exception as e:
                last_exc = e
                msg = str(e)
                transient = (
                    isinstance(e, RemoteDisconnected)
                    or isinstance(e, SSLError)
                    or "Connection aborted" in msg
                    or "RemoteDisconnected" in msg
                    or "EOF occurred" in msg
                    or "Max retries exceeded" in msg
                )

                if attempt >= 3:
                    # If final attempt and it's a transient/network issue, return 503 so clients
                    # can differentiate from an auth error; otherwise return 401.
                    if transient:
                        logger.error(f"Token verification failed (network): {e}")
                        raise AppError("Token verification failed due to network/SSL", 503)
                    else:
                        logger.error(f"Token verification failed: {e}")
                        raise AppError("Invalid or expired token", 401)

                if not transient:
                    logger.error(f"Token verification failed: {e}")
                    raise AppError("Invalid or expired token", 401)

                # Log and back off a little before retrying
                logger.info(f"Transient error verifying token (attempt {attempt}/3): {e} — retrying...")
                time.sleep(2 ** (attempt - 1))

    @staticmethod
    def signup(email, password, name, access_token):
        valid_keys = AuthService.get_valid_keys()
        if access_token not in valid_keys:
            raise AppError("Invalid Access Token", 403)

        try:
            user = auth.create_user(email=email, password=password, display_name=name)
            ref = db.reference(f"users/{user.uid}")
            ref.update({
                "email": email, 
                "name": name, 
                "verifiedAccess": True,
                "accessKey": access_token,
                "venues": {}
            })
            logger.info(f"User signed up: {user.uid}")
            return {"uid": user.uid}
        except Exception as e:
            logger.error(f"Signup error: {e}")
            raise AppError(str(e), 400)

    @staticmethod
    def login(email, password):
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={AuthService.API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}

        # Use a helper that retries on transient network errors
        return AuthService._post_with_retries(url, payload)

    @staticmethod
    def refresh_token(refresh_token):
        if not refresh_token:
            raise AppError("Missing refresh token", 400)
            
        url = f"https://securetoken.googleapis.com/v1/token?key={AuthService.API_KEY}"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        data = AuthService._post_with_retries(url, payload)

        # Keep behaviour and field naming compatible with previous implementation
        return {
            "idToken": data["id_token"],
            "refreshToken": data["refresh_token"],
            "expiresIn": data["expires_in"]
        }

    @staticmethod
    def get_profile(uid):
        try:
            ref = db.reference(f"users/{uid}")
            data = ref.get() or {}
            
            # Extract faults
            faults_value = ""
            venues = data.get("venues", {})
            for vname, vdata in venues.items():
                if isinstance(vdata, dict) and "faults" in vdata:
                    faults_value = vdata["faults"]
                    break
            
            return {
                "uid": uid,
                "email": data.get("email", ""),
                "name": data.get("name", ""),
                "venues": venues,
                "faults": faults_value,
                "verifiedAccess": data.get("verifiedAccess", False)
            }
        except Exception as e:
            logger.error(f"Get profile error: {e}")
            raise AppError("Unable to fetch profile", 500)

    @staticmethod
    def add_venue(uid, venue_name):
        if not AuthService._is_valid_db_key(venue_name):
            raise AppError("Invalid venue name", 400)
        
        try:
            parent_ref = db.reference(f"users/{uid}/venues")
            parent_ref.update({venue_name.strip(): {"__created": True}})
            
            # Verify write
            parent_val = parent_ref.get() or {}
            if venue_name.strip() not in parent_val:
                raise AppError("Venue creation failed (persistence check)", 500)
                
            logger.info(f"Venue added: {venue_name} for user {uid}")
            return {"venue": venue_name.strip()}
        except AppError:
            raise
        except Exception as e:
            logger.error(f"Add venue error: {e}")
            raise AppError("Unable to create venue", 500)

    @staticmethod
    def add_device(uid, venue, device, state="off"):
        state = AuthService.normalize_state(state) or "off"
        
        if not AuthService._is_valid_db_key(venue) or not AuthService._is_valid_db_key(device):
            raise AppError("Invalid venue or device name", 400)

        try:
            ref = db.reference(f"users/{uid}/venues/{venue.strip()}")
            # Check if venue exists
            if ref.get() is None:
                 raise AppError("Venue does not exist", 404)

            ref.update({device.strip(): state})
            logger.info(f"Device added: {device} to {venue} for user {uid}")
            return {"device": device.strip()}
        except AppError:
            raise
        except Exception as e:
            logger.error(f"Add device error: {e}")
            raise AppError("Unable to add device", 500)

    @staticmethod
    def update_device_state(uid, venue, device, value):
        new_state = AuthService.normalize_state(value)
        if new_state is None:
            raise AppError("Invalid device state; must be 'on', 'off', or '1-5'", 400)
            
        if not AuthService._is_valid_db_key(venue) or not AuthService._is_valid_db_key(device):
            raise AppError("Invalid venue or device name", 400)

        try:
            ref = db.reference(f"users/{uid}/venues/{venue.strip()}")
            ref.update({device.strip(): new_state})
            logger.info(f"Device state updated: {device} -> {new_state}")
            return {"value": new_state}
        except Exception as e:
            logger.error(f"Update device state error: {e}")
            raise AppError("Unable to update state", 500)

    @staticmethod
    def delete_venue(uid, venue):
        if not AuthService._is_valid_db_key(venue):
            raise AppError("Invalid venue name", 400)
            
        try:
            ref = db.reference(f"users/{uid}/venues/{venue.strip()}")
            ref.delete()
            logger.info(f"Venue deleted: {venue} for user {uid}")
            return {"venue": venue.strip()}
        except Exception as e:
            logger.error(f"Delete venue error: {e}")
            raise AppError("Unable to delete venue", 500)

    @staticmethod
    def delete_device(uid, venue, device):
        if not AuthService._is_valid_db_key(venue) or not AuthService._is_valid_db_key(device):
            raise AppError("Invalid venue or device name", 400)
            
        try:
            ref = db.reference(f"users/{uid}/venues/{venue.strip()}/{device.strip()}")
            ref.delete()
            logger.info(f"Device deleted: {device} from {venue} for user {uid}")
            return {"device": device.strip()}
        except Exception as e:
            logger.error(f"Delete device error: {e}")
            raise AppError("Unable to delete device", 500)

    @staticmethod
    def set_schedule(uid, venue, device, time, action, enabled=True):
        # DO NOT PARSE OR CONVERT TIME
        time_string = str(time).strip()  # preserve exactly what frontend sends

        try:
            ref = db.reference(f"users/{uid}/schedules/{venue}/{device}")
            ref.update({
                "time": time_string,
                "action": action,
                "status": "enable" if enabled else "disable"
            })
            logger.info(f"Schedule set: {venue}/{device} at {time_string}")
            return {"venue": venue, "device": device, "time": time_string, "action": action, "status": enabled}
        except Exception as e:
            logger.error(f"Set schedule error: {e}")
            raise AppError("Unable to set schedule", 500)


    @staticmethod
    def get_schedules(uid):
        try:
            ref = db.reference(f"users/{uid}/schedules")
            data = ref.get() or {}
            return data
        except Exception as e:
            logger.error(f"Get schedules error: {e}")
            raise AppError("Unable to fetch schedules", 500)

    @staticmethod
    def delete_schedule(uid, venue, device):
        if not AuthService._is_valid_db_key(venue) or not AuthService._is_valid_db_key(device):
            raise AppError("Invalid venue or device name", 400)
            
        try:
            ref = db.reference(f"users/{uid}/schedules/{venue}/{device}")
            ref.delete()
            logger.info(f"Schedule deleted: {venue}/{device}")
            return {"message": "Schedule deleted"}
        except Exception as e:
            logger.error(f"Delete schedule error: {e}")
            raise AppError("Unable to delete schedule", 500)

    @staticmethod
    def set_voice_key(uid, key):
        if not key:
            raise AppError("API key required", 400)
        try:
            ref = db.reference(f"users/{uid}/secure")
            ref.update({"gemini_key": key})
            logger.info(f"Voice key set for user {uid}")
            return {"message": "Key saved securely"}
        except Exception as e:
            logger.error(f"Set voice key error: {e}")
            raise AppError("Failed to save voice key", 500)

    @staticmethod
    def voice_key_exists(uid):
        try:
            secure = db.reference(f"users/{uid}/secure").get() or {}
            return bool(secure.get("gemini_key"))
        except Exception as e:
            logger.error(f"Check voice key error: {e}")
            raise AppError("Failed to check voice key", 500)

    @staticmethod
    def voice_command(uid, text):
        if not text:
            raise AppError("No text provided", 400)

        try:
            # Get API key
            secure = db.reference(f"users/{uid}/secure").get() or {}
            api_key = secure.get("gemini_key")
            if not api_key:
                raise AppError("No API key stored", 400)

            # Get context
            profile = db.reference(f"users/{uid}/venues").get() or {}
            venues = list(profile.keys())
            devices_map = {
                v: [d for d in profile[v].keys() if d not in ("__created", "faults")]
                for v in venues
            }

            payload = {
                "model": "gemini-2.0-flash",
                "contents": [{
                    "role": "user",
                    "parts": [{
                        "text": f"""
Allowed Venues: {json.dumps(venues)}
Allowed Devices: {json.dumps(devices_map)}

Convert this command into JSON:
{{"venue":"...", "device":"...", "value":"..."}}

Rules:
- Only use existing venue and device names
- Value must be "on", "off", or 1-5
- Support Tamil/English natural language
- Support ALL venue and ALL device handling
- If unknown, return null JSON
User command: "{text}"
Return STRICT JSON only.
"""
                    }]
                }]
            }

            res_json = AuthService._post_with_retries(
                f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={api_key}",
                payload,
                timeout=10
            )
            
            try:
                raw = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw = raw.replace("```json", "").replace("```", "")
                command_data = json.loads(raw)
            except (KeyError, IndexError, json.JSONDecodeError):
                logger.error(f"Gemini response parsing failed: {res_json}")
                raise AppError("Unable to parse Gemini response", 500)

            if not command_data.get("venue") or not command_data.get("device") or not command_data.get("value"):
                raise AppError("Not available in system", 400)

            # Execute
            db.reference(f"users/{uid}/venues/{command_data['venue']}").update({
                command_data["device"]: command_data["value"]
            })
            
            logger.info(f"Voice command executed: {command_data}")
            return {"message": "Action applied", **command_data}

        except AppError:
            raise
        except Exception as e:
            logger.error(f"Voice command error: {e}")
            raise AppError("Voice command processing failed", 500)
             

    @staticmethod
    def add_mon_venue(uid, venue, sensors):
        if not venue:
            raise AppError("Venue required", 400)
        if not isinstance(sensors, list) or not sensors:
            raise AppError("Sensor list required", 400)
            
        try:
            ref = db.reference(f"users/{uid}/monitoring_venues/{venue}")
            ref.update({s: "0" for s in sensors})
            logger.info(f"Monitoring venue added: {venue} for user {uid}")
            return {"message": "Monitoring venue created", "monitoring": ref.get()}
        except Exception as e:
            logger.error(f"Add monitoring venue error: {e}")
            raise AppError("Unable to add monitoring venue", 500)

    @staticmethod
    def _post_with_retries(url, payload, retries: int = 3, timeout: int = 5):
        """Helper to POST with retries for transient network/SSL errors.

        Returns parsed JSON on success or raises AppError.
        """
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                res = requests.post(url, json=payload, timeout=timeout)

                # Attempt to parse JSON even if an HTTP error code was returned
                data = res.json() if res.text else {}

                # If API reports an error in JSON payload, translate to AppError
                if isinstance(data, dict) and "error" in data:
                    # Keep original API error code as client-side 400 whenever present
                    raise AppError(data["error"].get("message", "API error"), 400)

                return data

            except SSLError as e:
                last_exc = e
                logger.error(f"SSL/network error contacting {url}: {e}")
            except requests.RequestException as e:
                last_exc = e
                logger.error(f"Network error contacting {url}: {e}")

            # Backoff before retrying
            if attempt < retries:
                sleep_for = 2 ** (attempt - 1)
                logger.info(f"Retrying request to {url} (attempt {attempt + 1}/{retries}) after {sleep_for}s")
                time.sleep(sleep_for)

        # If we fall through, rethrow a friendly AppError
        logger.error(f"All retries failed for POST {url}: {last_exc}")
        raise AppError("External service unreachable (network/SSL)", 503)

    @staticmethod
    def get_mon(uid):
        try:
            ref = db.reference(f"users/{uid}/monitoring_venues")
            return ref.get() or {}
        except Exception as e:
            logger.error(f"Get monitoring error: {e}")
            raise AppError("Unable to fetch monitoring data", 500)

    @staticmethod
    def delete_monitoring_venue(uid, venue):
        if not venue:
            raise AppError("Venue required", 400)
            
        try:
            ref = db.reference(f"users/{uid}/monitoring_venues/{venue}")
            ref.delete()
            logger.info(f"Monitoring venue deleted: {venue} for user {uid}")
            return {"message": "Monitoring venue deleted"}
        except Exception as e:
            logger.error(f"Delete monitoring venue error: {e}")
            raise AppError("Unable to delete monitoring venue", 500)

    @staticmethod
    def update_schedule_status(uid, venue, device, status):
        if not venue or not device or status not in ["enable", "disable"]:
            raise AppError("venue, device and valid status required", 400)
            
        try:
            ref = db.reference(f"users/{uid}/schedules/{venue}/{device}")
            ref.update({"status": status})
            logger.info(f"Schedule status updated: {venue}/{device} -> {status}")
            return {"venue": venue, "device": device, "status": status}
        except Exception as e:
            logger.error(f"Update schedule status error: {e}")
            raise AppError("Unable to update schedule status", 500)
    @staticmethod
    def save_fcm_token(uid, token):
      if not token:
        raise AppError("FCM token required", 400)

      try:
        ref = db.reference(f"users/{uid}")
        ref.update({"fcmToken": token})
        logger.info(f"FCM token saved for user {uid}")
        return {"message": "FCM token stored"}
      except Exception as e:
        logger.error(f"Save FCM token error: {e}")
        raise AppError("Unable to save FCM token", 500)
