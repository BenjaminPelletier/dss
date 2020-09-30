import os
import random


ENV_KEY_PREFIX = 'MOCKUSS'
ENV_KEY_BASE_URL = '{}_BASE_URL'.format(ENV_KEY_PREFIX)
ENV_KEY_AUTH = '{}_AUTH_SPEC'.format(ENV_KEY_PREFIX)
ENV_KEY_DSS = '{}_DSS_URL'.format(ENV_KEY_PREFIX)
ENV_KEY_DATABASE_PATH = '{}_DATABASE_PATH'.format(ENV_KEY_PREFIX)

# These keys map to entries in the Config class
KEY_SECRET_KEY = 'SECRET_KEY'
KEY_ADMIN_PASSWORD = 'ADMIN_PASSWORD'
KEY_BASE_URL = 'USS_BASE_URL'
KEY_DATABASE_PATH = 'DATABASE_PATH'
KEY_AUTH_SPEC = 'AUTH_SPEC'
KEY_DSS_URL = 'DSS_URL'


workspace_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'workspace')


def _get_secret_key():
  secret_key_file = os.path.join(workspace_path, 'secret_key.txt')
  if os.path.exists(secret_key_file):
    with open(secret_key_file, 'r') as f:
      return f.readline()
  secret_key = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(64))
  os.makedirs(os.path.dirname(secret_key_file), exist_ok=True)
  with open(secret_key_file, 'w') as f:
    f.write(secret_key)
  return secret_key


def _get_admin_password():
  admin_password_file = os.path.join(workspace_path, 'admin_password.txt')
  if os.path.exists(admin_password_file):
    with open(admin_password_file, 'r') as f:
      return f.readline()
  admin_password = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8))
  os.makedirs(os.path.dirname(admin_password_file), exist_ok=True)
  with open(admin_password_file, 'w') as f:
    f.write(admin_password)
  return admin_password


class Config(object):
  SECRET_KEY = _get_secret_key()
  ADMIN_PASSWORD = _get_admin_password()

  USS_BASE_URL = os.environ[ENV_KEY_BASE_URL]
  AUTH_SPEC = os.environ[ENV_KEY_AUTH]
  DSS_URL = os.environ[ENV_KEY_DSS]

  DATABASE_PATH = os.environ.get(ENV_KEY_DATABASE_PATH, workspace_path)

  WTF_CSRF_ENABLED = False # Can re-enable once nested forms pass CSRF validation
