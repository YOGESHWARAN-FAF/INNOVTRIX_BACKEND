from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables before importing config
load_dotenv()

from .config import config
from .firebase import initialize_firebase
from .utils.logger import logger
from .utils.error_handler import register_error_handlers

def create_app(config_name="default"):
    app = Flask(__name__)
    app.secret_key = "supersecretkey" # Required for session
    app.config.from_object(config[config_name])
    
    # Initialize CORS
    CORS(app)
    
    # Initialize Logger
    logger.info(f"Starting app in {config_name} mode")
    
    # Initialize Firebase
    with app.app_context():
        initialize_firebase()

    # Register Error Handlers
    register_error_handlers(app)

    # Register Blueprints
    from .routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from .routes.admin_routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/admin")
    
    # Health check
    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app
