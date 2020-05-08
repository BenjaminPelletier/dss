from flask import Flask

from app.auth.config import AuthorizationConfig
from app.scd.config import ScdConfig
from app.scd.memory_storage import MemoryScdStorage


webapp = Flask(__name__)
webapp.config.from_object(ScdConfig)
webapp.config.from_object(AuthorizationConfig)

scd_storage = MemoryScdStorage()

from app import routes
