import os
import random


workspace_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'workspace')


def _get_secret_key():
  secret_key_file = os.path.join(workspace_path, 'secret_key.txt')
  if os.path.exists(secret_key_file):
    with open(secret_key_file, 'r') as f:
      return f.readline()
  secret_key = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(64))
  with open(secret_key_file, 'w') as f:
    f.write(secret_key)
  return secret_key


def _get_admin_password():
  admin_password_file = os.path.join(workspace_path, 'admin_password.txt')
  if os.path.exists(admin_password_file):
    with open(admin_password_file, 'r') as f:
      return f.readline()
  admin_password = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(8))
  with open(admin_password_file, 'w') as f:
    f.write(admin_password)
  return admin_password


class Config(object):
  SECRET_KEY = _get_secret_key()
  ADMIN_PASSWORD = _get_admin_password()

  USS_BASE_URL = os.environ['USS_BASE_URL']

  DATABASE_PATH = os.environ.get('USS_DATABASE_PATH', workspace_path)

  WTF_CSRF_ENABLED = False # Can re-enable once nested forms pass CSRF validation
