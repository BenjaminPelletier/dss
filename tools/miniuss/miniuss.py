"""A simulated USS exposing TCL4 endpoints.

Copyright 2018 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import jwt
import logging
import sys

import flask
import requests
from rest_framework import status

import config
import interuss_platform
import operations

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('MiniUss')
log.setLevel(logging.DEBUG)
webapp = flask.Flask(__name__)  # Global object serving the API


# interuss_platform.Client managing communication with InterUSS Platform grid.
grid_client = None

# operations.Manager managing operations for this USS.
operations_manager = None

# Public key for validating access tokens at USS endpoints.
public_key = None

# Content that must be in Authorization header to use control endpoints.
control_authorization = None


def _update_operations():
  """Replace Operator entry in grid with current set of Operations."""
  try:
    grid_client.upsert_operator(operations_manager.get_operations())
  except requests.HTTPError as e:
    msg = ('Error updating InterUSS Platform Operator entry: ' +
           e.response.content)
    flask.abort(e.response.status_code, msg)


def _error(status_code, content):
  log.error('%d: %s', status_code, content)
  return content, status_code


# == Control and status endpoints ==

@webapp.route('/', methods=['GET'])
@webapp.route('/status', methods=['GET'])
def status_endpoint():
  log.debug('Status requested')
  return flask.jsonify({
    'status': 'success',
    'operations': [{'gufi': op.operation['gufi'], 'hidden': op.hidden}
                   for op in operations_manager.get_managed_operations()],
    'uss_baseurl': grid_client.uss_baseurl})


@webapp.route('/client/operation', methods=['POST', 'PUT'])
def upsert_operation_endpoint():
  log.debug('Operation upsert requested')
  _validate_control()
  operation = flask.request.json
  operations_manager.upsert_operation(operation)
  _update_operations()
  return flask.jsonify({'status': 'success',
                        'operation': operation})


@webapp.route('/client/operation/<gufi>', methods=['DELETE'])
def delete_operation_endpoint(gufi):
  log.debug('Operation deletion requested: %s', gufi)
  _validate_control()
  try:
    operations_manager.remove_operation(gufi)
  except KeyError:
    return _error(status.HTTP_404_NOT_FOUND, 'GUFI %s not found' % gufi)
  _update_operations()
  return flask.jsonify({'status': 'success'})


# == USS endpoints ==

@webapp.route('/uvrs/<message_id>', methods=['PUT'])
def uvrs_endpoint(message_id):
  log.debug('USS/uvrs notified of UVR message ID %s', message_id)
  _validate_access_token()
  return '', status.HTTP_204_NO_CONTENT


@webapp.route('/utm_messages/<message_id>', methods=['PUT'])
def utm_messages_endpoint(message_id):
  log.debug('USS/utm_messages notified of UTM message ID %s', message_id)
  _validate_access_token()
  return '', status.HTTP_204_NO_CONTENT


@webapp.route('/uss/<uss_instance_id>', methods=['PUT'])
def uss_instances_endpoint(uss_instance_id):
  log.debug('USS/uss notified of USS instance ID %s', uss_instance_id)
  _validate_access_token()
  return '', status.HTTP_204_NO_CONTENT


@webapp.route('/negotiations/<message_id>', methods=['PUT'])
def negotiations_endpoint(message_id):
  log.debug('USS/negotiations request received with message ID %s', message_id)
  _validate_access_token()
  return '', status.HTTP_204_NO_CONTENT


@webapp.route('/positions/<position_id>', methods=['PUT'])
def positions_endpoint(position_id):
  log.debug('USS/positions notified with position ID %s', position_id)
  _validate_access_token()
  return '', status.HTTP_204_NO_CONTENT


@webapp.route('/operations', methods=['GET'])
def get_operations_endpoint():
  log.debug('USS/operations queried')
  _validate_access_token()
  operations = operations_manager.get_operations()
  return flask.jsonify(operations)


@webapp.route('/operations/<gufi>', methods=['GET', 'PUT'])
def operation_endpoint(gufi):
  _validate_access_token()
  if flask.request.method == 'GET':
    log.debug('USS/operations/gufi queried for GUFI %s', gufi)
    try:
      operation = operations_manager.get_operation(gufi)
    except KeyError:
      flask.abort(status.HTTP_404_NOT_FOUND, 'No operation with GUFI ' + gufi)
    return flask.jsonify(operation)
  elif flask.request.method == 'PUT':
    log.debug('Received operation notification with GUFI %s', gufi)
    return '', status.HTTP_204_NO_CONTENT
  else:
    flask.abort(status.HTTP_405_METHOD_NOT_ALLOWED)


@webapp.route('/enhanced/operations/<gufi>', methods=['GET', 'PUT'])
def enhanced_operation_endpoint(gufi):
  log.debug('USS/enhanced/operations queried for GUFI %s', gufi)
  _validate_access_token()
  flask.abort(status.HTTP_500_INTERNAL_SERVER_ERROR,
              'Enhanced operations endpoint not yet supported')


@webapp.before_first_request
def before_first_request():
  if control_authorization is None:
    initialize([])


def _validate_control():
  """Return an error response if no authorization to control this USS."""
  if 'Authorization' not in flask.request.headers:
    msg = 'Authorization header was not included in request'
    log.error(msg)
    flask.abort(status.HTTP_401_UNAUTHORIZED, msg)
  if flask.request.headers['Authorization'] != control_authorization:
    msg = 'Not authorized to access this control endpoint'
    log.error(msg)
    flask.abort(status.HTTP_403_FORBIDDEN, msg)


def _validate_access_token(allowed_scopes=None):
  """Return an error response if the provided access token is invalid."""
  if 'Authorization' in flask.request.headers:
    token = flask.request.headers['Authorization'].replace('Bearer ', '')
  elif 'access_token' in flask.request.headers:
    token = flask.request.headers['access_token']
  else:
    flask.abort(status.HTTP_401_UNAUTHORIZED,
                'Access token was not included in request')

  try:
    claims = jwt.decode(token, public_key, algorithms='RS256')
  except jwt.ExpiredSignatureError:
    msg = 'Access token is invalid: token has expired.'
    log.error(msg)
    flask.abort(status.HTTP_401_UNAUTHORIZED, msg)
  except jwt.DecodeError:
    log.error('Access token is invalid and cannot be decoded.')
    flask.abort(status.HTTP_400_BAD_REQUEST,
                'Access token is invalid: token cannot be decoded.')

  if (allowed_scopes is not None and
      not set(claims['scope']).intersection(set(allowed_scopes))):
    flask.abort(status.HTTP_403_FORBIDDEN, 'Scopes included in access token do '
                                           'not grant access to this resource')


def initialize(argv):
  log.debug('Debug-level log messages are visible')
  options = config.parse_options(argv)

  global control_authorization
  control_authorization = options.control_authorization

  global public_key
  if options.authpublickey.startswith('http'):
    log.info('Downloading auth public key from ' + options.authpublickey)
    response = requests.get(options.authpublickey)
    response.raise_for_status()
    public_key = response.content
  else:
    public_key = options.authpublickey
  public_key = public_key.replace(' PUBLIC ', '_PLACEHOLDER_')
  public_key = public_key.replace(' ', '\n')
  public_key = public_key.replace('_PLACEHOLDER_', ' PUBLIC ')

  global grid_client
  grid_client = interuss_platform.Client(
    options.nodeurl, int(options.zoom), options.authurl, options.username,
    options.password, options.baseurl)

  global operations_manager
  operations_manager = operations.Manager()

  return options


def main(argv):
  options = initialize(argv)

  log.info('Starting webserver...')
  webapp.run(host=options.server, port=int(options.port))


# This is what starts everything when run directly as an executable
if __name__ == '__main__':
  main(sys.argv)
