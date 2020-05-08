import logging
import sys

import flask
from werkzeug.exceptions import HTTPException

from app import webapp
from app.auth import authorization
from app.scd import scd

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('DSS')


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


def main(argv):
  del argv

  log.info('Starting webserver...')
  webapp.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
  main(sys.argv)
