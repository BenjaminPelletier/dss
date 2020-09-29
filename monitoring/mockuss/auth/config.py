import json
import os

import jwcrypto.jwk
import requests


ENV_KEY_PREFIX = 'MOCKUSS'
ENV_KEY_PUBLIC_KEY = '{}_PUBLIC_KEY'.format(ENV_KEY_PREFIX)
ENV_KEY_TOKEN_AUDIENCE = '{}_TOKEN_AUDIENCE'.format(ENV_KEY_PREFIX)

# These keys map to entries in the AuthorizationConfig class
KEY_TOKEN_PUBLIC_KEY = 'TOKEN_PUBLIC_KEY'
KEY_TOKEN_AUDIENCE = 'TOKEN_AUDIENCE'


def fix_key(public_key: str) -> str:
  if public_key.startswith('http://') or public_key.startswith('https://'):
    resp = requests.get(public_key)
    if public_key.endswith('.json'):
      key = resp.json()
      if 'keys' in key:
        key = key['keys'][0]
      jwk = jwcrypto.jwk.JWK.from_json(json.dumps(key))
      public_key = jwk.export_to_pem().decode('utf-8')
    else:
      public_key = resp.content.decode('utf-8')
  # ENV variables sometimes don't pass newlines, spec says white space
  # doesn't matter, but pyjwt cares about it, so fix it
  public_key = public_key.replace(' PUBLIC ', '_PLACEHOLDER_')
  public_key = public_key.replace(' ', '\n')
  public_key = public_key.replace('_PLACEHOLDER_', ' PUBLIC ')
  return public_key


class AuthorizationConfig(object):
  TOKEN_PUBLIC_KEY = fix_key(os.environ.get(ENV_KEY_PUBLIC_KEY, '')).encode('utf-8')
  TOKEN_AUDIENCE = os.environ.get(ENV_KEY_TOKEN_AUDIENCE, '')
