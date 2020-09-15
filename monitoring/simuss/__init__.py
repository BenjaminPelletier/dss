import flask
import flask_login

from .auth.config import AuthorizationConfig
from .config import Config
from .database import Database

login_manager = flask_login.LoginManager()
login_manager.login_view = 'login'

webapp = flask.Flask(__name__)

webapp.config.from_object(Config)
webapp.config.from_object(AuthorizationConfig)

db = Database(webapp.config['DATABASE_PATH'])
login_manager.init_app(webapp)

from monitoring.simuss import routes
