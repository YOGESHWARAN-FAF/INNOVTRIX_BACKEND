from flask import Blueprint, request, jsonify
from ..services.auth_service import AuthService
from ..utils.response import success_response, error_response
from ..utils.error_handler import AppError
from functools import wraps

auth_bp = Blueprint("auth", __name__)

def get_uid():
    token = request.headers.get("Authorization", "")
    return AuthService.verify_token(token)

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            uid = get_uid()
            
            # Enforce verifiedAccess
            profile = AuthService.get_profile(uid)
            if not profile.get("verifiedAccess"):
                return jsonify({"error": "Access Denied: No License Token"}), 403

            return f(uid, *args, **kwargs)
        except AppError as e:
            return jsonify({"error": e.message}), e.status_code
        except Exception as e:
            return jsonify({"error": "Unauthorized"}), 401
    return decorated_function

@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.json or {}
    try:
        result = AuthService.signup(
            data.get("email"), 
            data.get("password"), 
            data.get("name", ""),
            data.get("accessToken")
        )
        return jsonify(result), 200
    except AppError as e:
        return jsonify({"error": e.message}), e.status_code

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    try:
        result = AuthService.login(data.get("email"), data.get("password"))
        return jsonify(result), 200
    except AppError as e:
        return jsonify({"error": e.message}), e.status_code

@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.json or {}
    try:
        result = AuthService.refresh_token(data.get("refreshToken"))
        return jsonify(result), 200
    except AppError as e:
        return jsonify({"error": e.message}), e.status_code

@auth_bp.route("/profile", methods=["GET"])
@require_auth
def profile(uid):
    result = AuthService.get_profile(uid)
    return jsonify(result), 200
@auth_bp.route("/save_fcm_token", methods=["POST"])
@require_auth
def save_fcm_token(uid):
    data = request.json or {}
    token = data.get("token")

    if not token:
        return jsonify({"error": "FCM token required"}), 400

    result = AuthService.save_fcm_token(uid, token)
    return jsonify(result), 200

@auth_bp.route("/add_venue", methods=["POST"])
@require_auth
def add_venue(uid):
    data = request.json or {}
    result = AuthService.add_venue(uid, data.get("venue"))
    return jsonify({"message": "Venue added", **result}), 200

@auth_bp.route("/add_device", methods=["POST"])
@require_auth
def add_device(uid):
    data = request.json or {}
    result = AuthService.add_device(uid, data.get("venue"), data.get("device"), data.get("state", "off"))
    return jsonify({"message": "Device added", **result}), 200

@auth_bp.route("/device_state", methods=["POST"])
@require_auth
def device_state(uid):
    data = request.json or {}
    result = AuthService.update_device_state(uid, data.get("venue"), data.get("device"), data.get("value"))
    return jsonify({"message": "Updated", **result}), 200

@auth_bp.route("/delete_venue", methods=["DELETE"])
@require_auth
def delete_venue(uid):
    data = request.json or {}
    result = AuthService.delete_venue(uid, data.get("venue"))
    return jsonify({"message": "Venue deleted", **result}), 200

@auth_bp.route("/delete_device", methods=["DELETE"])
@require_auth
def delete_device(uid):
    data = request.json or {}
    result = AuthService.delete_device(uid, data.get("venue"), data.get("device"))
    return jsonify({"message": "Device deleted", **result}), 200

@auth_bp.route("/set_schedule", methods=["POST"])
@require_auth
def set_schedule(uid):
    data = request.json or {}
    result = AuthService.set_schedule(
        uid, 
        data.get("venue"), 
        data.get("device"), 
        data.get("time"), 
        data.get("action")
    )
    return jsonify(result), 200

@auth_bp.route("/get_schedules", methods=["GET"])
@require_auth
def get_schedules(uid):
    result = AuthService.get_schedules(uid)
    return jsonify({"schedules": result}), 200

@auth_bp.route("/delete_schedule", methods=["DELETE"])
@require_auth
def delete_schedule(uid):
    data = request.json or {}
    result = AuthService.delete_schedule(uid, data.get("venue"), data.get("device"))
    return jsonify(result), 200

@auth_bp.route("/set_voice_key", methods=["POST"])
@require_auth
def set_voice_key(uid):
    data = request.json or {}
    result = AuthService.set_voice_key(uid, data.get("apiKey"))
    return jsonify(result), 200

@auth_bp.route("/voice_key_exists", methods=["GET"])
@require_auth
def voice_key_exists(uid):
    exists = AuthService.voice_key_exists(uid)
    return jsonify({"exists": exists}), 200

@auth_bp.route("/voice_command", methods=["POST"])
@require_auth
def voice_command(uid):
    data = request.json or {}
    result = AuthService.voice_command(uid, data.get("text"))
    return jsonify(result), 200
# ------------ ADD SENSOR MONITORING VENUE ------------
@auth_bp.route("/add_monitoring_venue", methods=["POST"])
@require_auth
def add_monitoring_venue(uid):
    data = request.json or {}
    venue = data.get("venue")
    sensors = data.get("sensors", [])

    if not venue:
        return jsonify({"error": "Venue required"}), 400
    if not isinstance(sensors, list) or not sensors:
        return jsonify({"error": "Sensor list required"}), 400

    result = AuthService.add_mon_venue(uid, venue, sensors)
    return jsonify(result), 200


# ------------ GET MONITORING DATA ------------
@auth_bp.route("/get_monitoring_data", methods=["GET"])
@require_auth
def get_monitoring_data(uid):
    result = AuthService.get_mon(uid)
    return jsonify({"monitoring": result}), 200
# ------------ DELETE MONITORING VENUE ------------
@auth_bp.route("/delete_monitoring_venue", methods=["DELETE"])
@require_auth
def delete_monitoring_venue(uid):
    data = request.json or {}
    venue = data.get("venue")

    if not venue:
        return jsonify({"error": "Venue required"}), 400

    result = AuthService.delete_monitoring_venue(uid, venue)
    return jsonify(result), 200
# ---------- ENABLE/DISABLE SCHEDULE ----------
@auth_bp.route("/update_schedule_status", methods=["POST"])
@require_auth
def update_schedule_status(uid):
    data = request.json or {}
    venue = data.get("venue")
    device = data.get("device")
    status = data.get("status")  # "enable" or "disable"

    if not venue or not device or status not in ["enable", "disable"]:
        return jsonify({"error": "venue, device and valid status required"}), 400

    result = AuthService.update_schedule_status(uid, venue, device, status)
    return jsonify({"message": "Schedule status updated", **result}), 200
