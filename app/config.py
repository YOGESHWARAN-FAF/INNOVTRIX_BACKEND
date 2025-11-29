import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")
    DEBUG = False
    TESTING = False
    FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    # Caching Config
    CACHE_TYPE = "SimpleCache"  # Use 'RedisCache' for production
    CACHE_DEFAULT_TIMEOUT = 300

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    # Security headers, etc.
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    
    # Example Redis Config (commented out)
    # CACHE_TYPE = "RedisCache"
    # CACHE_REDIS_URL = os.getenv("REDIS_URL")

class TestingConfig(Config):
    TESTING = True
    DEBUG = True

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}
