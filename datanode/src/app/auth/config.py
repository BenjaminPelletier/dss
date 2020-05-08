import os

def _fix_key(public_key: str) -> str:
  # ENV variables sometimes don't pass newlines, spec says white space
  # doesn't matter, but pyjwt cares about it, so fix it
  public_key = public_key.replace(' PUBLIC ', '_PLACEHOLDER_')
  public_key = public_key.replace(' ', '\n')
  public_key = public_key.replace('_PLACEHOLDER_', ' PUBLIC ')
  return public_key


class AuthorizationConfig(object):
  TOKEN_PUBLIC_KEY = _fix_key(os.environ.get('TOKEN_PUBLIC_KEY', '')).encode('utf-8')
