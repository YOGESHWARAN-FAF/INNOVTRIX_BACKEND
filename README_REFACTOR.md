# Refactoring & Production Guide

## 1. New Folder Structure

```
backend/
│── app/
│   ├── routes/
│   │   └── auth_routes.py       # Clean routes, calls services
│   ├── services/
│   │   └── auth_service.py      # Business logic & Firebase calls
│   ├── utils/
│   │   ├── response.py          # Standard API responses
│   │   ├── logger.py            # Centralized logging
│   │   └── error_handler.py     # Global exception handling
│   ├── config.py                # Environment configurations
│   ├── firebase.py              # Firebase initialization
│   └── __init__.py              # App factory
│
├── logs/                        # Log files (auto-created)
├── scheduler.py                 # Background scheduler
├── run.py                       # Entry point
├── requirements.txt
└── .env
```

## 2. Key Improvements

- **Service Layer**: Business logic is now in `AuthService`, making routes clean and testable.
- **Global Error Handling**: `AppError` class and global handler ensure consistent error JSON responses.
- **Logging**: Rotating file logs in `logs/app.log` instead of `print()`.
- **Configuration**: `DevelopmentConfig` and `ProductionConfig` in `config.py`.
- **Security**: `require_auth` decorator for protected routes.

## 3. Performance & Optimization Tips

### Firebase Optimization
- **Indexing**: Add `.indexOn` rules in Firebase Realtime Database for fields you query often (e.g., `email`, `venue`).
- **Shallow Queries**: Use `shallow=True` when you only need keys, not values.
- **Asynchronous Calls**: For heavy writes, consider using Python `asyncio` with an async Firebase wrapper or offload to a task queue.

### Caching
- **Flask-Caching**: Install `Flask-Caching`.
  ```python
  from flask_caching import Cache
  cache = Cache(app, config={'CACHE_TYPE': 'RedisCache', 'CACHE_REDIS_URL': '...'})
  
  @auth_bp.route('/profile')
  @cache.cached(timeout=60, query_string=True)
  def profile(uid): ...
  ```
- **Redis**: Use Redis for session storage and caching frequent reads (like user profiles).

### Rate Limiting
- **Flask-Limiter**: Protect APIs from abuse.
  ```python
  from flask_limiter import Limiter
  from flask_limiter.util import get_remote_address
  
  limiter = Limiter(app, key_func=get_remote_address)
  
  @auth_bp.route("/login", methods=["POST"])
  @limiter.limit("5 per minute")
  def login(): ...
  ```

### Background Tasks
- **Celery**: For heavy tasks (e.g., sending emails, processing large data), use Celery with Redis/RabbitMQ.
- **Current Scheduler**: The current `scheduler.py` runs in a thread. For production, run it as a separate process (worker) to avoid blocking the main web server if it gets heavy.

## 4. Production Deployment

### Gunicorn (Application Server)
Do not use `python run.py` in production. Use Gunicorn.
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 run:app
```
- `-w 4`: 4 worker processes (adjust based on CPU cores: 2 * cores + 1).

### Nginx (Reverse Proxy)
Set up Nginx in front of Gunicorn to handle SSL, static files, and buffering.

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Environment Variables
Ensure `.env` is not committed to git. Use a secrets manager in production.
