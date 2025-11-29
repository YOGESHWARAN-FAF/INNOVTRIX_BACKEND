from flask import jsonify
from .logger import logger

class AppError(Exception):
    """Custom Exception Class for Application Errors"""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

def register_error_handlers(app):
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        logger.error(f"AppError: {error.message}")
        # Return error in a format that might be compatible with both or just standard
        # For global errors, we'll stick to the requested standard but include 'error' key for compat
        response = {
            "status": "error",
            "message": error.message,
            "error": error.message # Backward compatibility
        }
        if error.payload:
            response["payload"] = error.payload
        return jsonify(response), error.status_code

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"status": "error", "message": "Resource not found", "error": "Not Found"}), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        logger.critical(f"Internal Server Error: {error}")
        return jsonify({"status": "error", "message": "Internal Server Error", "error": "Internal Server Error"}), 500

    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        logger.exception(f"Unhandled Exception: {error}")
        return jsonify({"status": "error", "message": "An unexpected error occurred", "error": str(error)}), 500
