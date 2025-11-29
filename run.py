from dotenv import load_dotenv
import os

# Load env vars first
load_dotenv()

from app import create_app
from threading import Thread
from scheduler import run_scheduler

# Get environment from env var or default to development
env = os.getenv("FLASK_ENV", "development")
app = create_app(env)

def start_scheduler():
    print("Scheduler started...")
    run_scheduler()

if __name__ == "__main__":
    # Start scheduler in background thread
    # Note: In production with Gunicorn, this might need a separate worker or Celery
    scheduler_thread = Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
