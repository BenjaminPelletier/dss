import os

import requests


def fix_key(public_key: str) -> str:
  if public_key.startswith('http://') or public_key.startswith('https://'):
    resp = requests.get(public_key)
    public_key = resp.content
  # ENV variables sometimes don't pass newlines, spec says white space
  # doesn't matter, but pyjwt cares about it, so fix it
  public_key = public_key.replace(' PUBLIC ', '_PLACEHOLDER_')
  public_key = public_key.replace(' ', '\n')
  public_key = public_key.replace('_PLACEHOLDER_', ' PUBLIC ')
  return public_key


class AuthorizationConfig(object):
  TOKEN_PUBLIC_KEY = fix_key(os.environ.get('USS_PUBLIC_KEY', '')).encode('utf-8')
  TOKEN_AUDIENCE = os.environ.get('USS_TOKEN_AUDIENCE', '')
