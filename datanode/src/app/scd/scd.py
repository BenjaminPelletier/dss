import logging

import flask

from app import webapp
from app.scd import errors


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('SCD')

VERSION = 'SCD0.0.1'

@webapp.route('/dss/v1/status', methods=['GET'])
def Status():
  log.debug('Status handler instantiated...')
  return flask.jsonify({'status': 'success',
                        'message': 'OK',
                        'version': VERSION})


# Import declared endpoints
from . import subscription_endpoints
from . import operation_endpoints


def handle_exception(e):
  if isinstance(e, errors.NotFoundError):
    return flask.jsonify({'message': e.message}), 404
  elif isinstance(e, errors.NotOwnedError):
    return flask.jsonify({'message': e.message}), 403

  return None
