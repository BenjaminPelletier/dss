import flask
import flask_login

import monitoring.monitorlib
import monitoring.monitorlib.auth
import monitoring.monitorlib.infrastructure
from .auth.config import AuthorizationConfig
from .config import Config, KEY_DATABASE_PATH, KEY_AUTH_SPEC, KEY_DSS_URL
from .database import Database

login_manager = flask_login.LoginManager()
login_manager.login_view = 'login'

webapp = flask.Flask(__name__)

webapp.config.from_object(Config)
webapp.config.from_object(AuthorizationConfig)

db = Database(webapp.config[KEY_DATABASE_PATH])
login_manager.init_app(webapp)

_auth_adapter = monitoring.monitorlib.auth.make_auth_adapter(webapp.config[KEY_AUTH_SPEC])
utm_client = monitoring.monitorlib.infrastructure.DSSTestSession(webapp.config[KEY_DSS_URL], _auth_adapter)

from monitoring.mockuss import routes
