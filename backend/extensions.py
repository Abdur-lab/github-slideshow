from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from apscheduler.schedulers.background import BackgroundScheduler

db = SQLAlchemy()
csrf = CSRFProtect()
cache = Cache()
limiter = Limiter(key_func=get_remote_address)
scheduler = BackgroundScheduler(daemon=True)
