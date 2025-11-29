from app import create_app
import os

env = os.getenv("FLASK_ENV", "production")
app = create_app(env)

if __name__ == "__main__":
    app.run()
