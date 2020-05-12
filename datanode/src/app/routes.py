import flask
from werkzeug.exceptions import HTTPException

from app import webapp
from app.auth import authorization


@webapp.route('/status')
def status():
  return 'Ok'


@webapp.errorhandler(Exception)
def handle_exception(e):
  result = scd.handle_exception(e)
  if result is not None:
    return result

  if isinstance(e, HTTPException):
    return e
  elif isinstance(e, authorization.InvalidScopeError):
    return flask.jsonify({
      'message': 'Invalid scope; expected one of {%s}, but received only {%s}' % (' '.join(e.permitted_scopes),
                                                                                  ' '.join(e.provided_scopes))}), 403
  elif isinstance(e, authorization.InvalidAccessTokenError):
    return flask.jsonify({'message': e.message}), 401
  elif isinstance(e, authorization.ConfigurationError):
    return flask.jsonify({'message': e.message}), 500
  elif isinstance(e, ValueError):
    return flask.jsonify({'message': str(e)}), 400

  return flask.jsonify({'message': str(e)}), 500


from .scd import scd
