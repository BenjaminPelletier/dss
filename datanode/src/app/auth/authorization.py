import collections
from functools import wraps
import logging
import flask
import jwt

from app import webapp


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('Authorization')


Authorization = collections.namedtuple('Authorization', ['client_id', 'scopes', 'issuer'])


class InvalidScopeError(Exception):
  def __init__(self, permitted_scopes, provided_scopes):
    self.permitted_scopes = permitted_scopes
    self.provided_scopes = provided_scopes


class InvalidAccessTokenError(Exception):
  def __init__(self, message):
    self.message = message


class ConfigurationError(Exception):
  def __init__(self, message):
    self.message = message


def requires_scope(permitted_scopes):
  """
  A decorator to protect a Flask endpoint.
  If you decorate an endpoint with this, it will ensure that the requester has
  a valid access token with the required scope before allowing the endpoint to
  be called.
  """
  def outer_wrapper(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
      if hasattr(flask.request, 'jwt'):
        # Token has already been processed; check additional scope
        has_scope = False
        for scope in permitted_scopes:
          if scope in flask.request.jwt.scopes:
            has_scope = True
            break
        if not has_scope:
          raise InvalidScopeError(permitted_scopes, flask.request.jwt.scopes)
      else:
        # Token has not yet been processed; process it
        token = flask.request.headers.get('Authorization', None)
        if token is None:
          raise InvalidAccessTokenError('Missing Authorization header')
        token = token.replace('Bearer ', '')
        try:
          public_key = webapp.config.get('TOKEN_PUBLIC_KEY', None)
          if not public_key:
            raise ConfigurationError('Public key for access tokens is not configured on server')
          aud = webapp.config.get('TOKEN_AUDIENCE', None)
          if not aud:
            raise ConfigurationError('Audience for access tokens is not configured on server')
          r = jwt.decode(token, public_key, algorithms='RS256', audience=aud)
          provided_scopes = r['scope'].split(' ')
          has_scope = False
          for scope in permitted_scopes:
            if scope in provided_scopes:
              has_scope = True
              break
          if not has_scope:
            raise InvalidScopeError(permitted_scopes, provided_scopes)
          client_id = r['client_id'] if 'client_id' in r else r.get('sub', None)
        except jwt.ImmatureSignatureError:
          raise InvalidAccessTokenError('Access token is immature.')
        except jwt.ExpiredSignatureError:
          raise InvalidAccessTokenError('Access token has expired.')
        except jwt.InvalidSignatureError:
          raise InvalidAccessTokenError('Access token signature is invalid.')
        except jwt.DecodeError:
          raise InvalidAccessTokenError('Access token cannot be decoded.')
        except jwt.InvalidTokenError as e:
          raise InvalidAccessTokenError('Unexpected InvalidTokenError: %s' % str(e))
        issuer = r.get('iss', None)
        flask.request.jwt = Authorization(client_id, provided_scopes, issuer)

      return fn(*args, **kwargs)
    return wrapper
  return outer_wrapper
