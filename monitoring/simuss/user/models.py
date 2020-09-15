from typing import Optional

import flask_login
from werkzeug.security import generate_password_hash, check_password_hash

from monitoring.simuss import login_manager, webapp


class User(flask_login.UserMixin):
  def __init__(self, username: str):
    self.username = username
    self.id = username
    self.set_password(webapp.config['ADMIN_PASSWORD'] if username == 'admin' else None)

  def __repr__(self):
    return '<User {}>'.format(self.username)

  def set_password(self, password):
    self.password_hash = generate_password_hash(password) if password else None

  def check_password(self, password):
    return check_password_hash(self.password_hash, password) if self.password_hash else False


@login_manager.user_loader
def load_user(id):
  return User(id)
