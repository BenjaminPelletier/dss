"""The InterUSS Platform Data Node storage API server.

This flexible and distributed system is used to connect multiple USSs operating
in the same general area to share safety information while protecting the
privacy of USSs, businesses, operator and consumers. The system is focused on
facilitating communication amongst actively operating USSs with no details about
UAS operations stored or processed on the InterUSS Platform.

A data node contains all of the API, logic, and data consistency infrastructure
required to perform CRUD (Create, Read, Update, Delete) operations on specific
grid cells. Multiple data nodes can be executed to increase resilience and
availability. This is achieved by a stateless API to service USSs, an
information interface to translate grid cell USS information into the correct
data storage format, and an information consistency store to ensure data is up
to date.

This module is the stateless API to service USSs.


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
# logging is our log infrastructure used for this application
import collections
import datetime
import logging
# OptionParser is our command line parser interface
from optparse import OptionParser
import os
import random
import sys
import threading

# Flask is our web services infrastructure
from flask import abort
from flask import Flask
from flask import jsonify
from flask import request
# rest_framework is for HTTP status codes
from rest_framework import status
import iso8601
import pytz
import s2sphere

# Tools for checking client authorization
import authorization

# Initialize everything we need
# VERSION = '0.1.0'  # Initial TCL3 release
# VERSION = '0.1.1'  # Pythonized file names and modules
# VERSION = '0.1.2'  # Added OS Environment Variables in addition to cmd line
# VERSION = '0.1.3'  # Added server reconnection logic on lost session
# VERSION = '0.1.4'  # Added utility function to convert lat/lon to slippy
# VERSION = '0.2.0'  # Added OAuth access_token validation
# VERSION = '0.2.1'  # Changed uss_id to use client_id field from NASA
# VERSION = '0.2.2'  # Updated parameter parsing to support swaggerhub
# VERSION = '0.2.3'  # Update overall timestamp in locking metadata on change
# VERSION = '0.2.4'  # Fixed incorrect failed assertion with zero numbered tiles
# VERSION = '0.3.0'  # Changed to locally verifying JWT, removing NASA FIMS link
# VERSION = '0.3.1'  # Added token validation option in test mode
# VERSION = '0.4.0'  # Changed data structure to match v1 of InterUSS Platform
# VERSION = '1.0.0'  # Initial, approved release deployed on GitHub
# VERSION = '1.0.1.001'  # Bug fixes for slippy, dates, and OAuth key
# VERSION = '1.0.2.001'  # Refactored to run with gunicorn
# VERSION = '1.0.2.002'  # Standardize OAuth Authorization header, docker fix
# VERSION = '1.0.2.003'  # slippy utility updates to support point/path/polygon
# VERSION = '1.0.2.004'  # slippy non-breaking api changes to support path/polygon
# VERSION = '1.1.0.005'  # api changes to support multi-grid GET/PUT/DEL
# VERSION = 'PublicPortal1.1.1.006'  # Added public portal support
# VERSION = 'PublicPortal1.1.1.007'  # Fixed multi-cell bug
# VERSION = 'PublicPortal1.1.2.008'  # Added per-area auth
VERSION = 'ASTMStub2.0.0.009'  # Switched to ASTM format without data sync backing

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('InterUSS_DataNode_StorageAPI')
webapp = Flask(__name__)  # Global object serving the API
auth = None  # Global object providing authorization


EntityReference = collections.namedtuple('EntityReference', ('id', 'data', 'cell_ids', 'time_start', 'time_end'))

class EntityCollection(object):
  def __init__(self):
    self._ids_by_cell_id = collections.defaultdict(set)
    self._entities_by_id = {}

  def list_from_cells(self, cell_ids, earliest_time=None, latest_time=None):
    entity_ids = set()
    for cell_id in cell_ids:
      cell_id_str = str(cell_id)
      if cell_id_str not in self._ids_by_cell_id:
        continue
      entity_ids = entity_ids.union(self._ids_by_cell_id[cell_id_str])

    result = []
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    for entity_id in entity_ids:
      entity = self._entities_by_id[entity_id]
      if entity.time_end and now > entity.time_end:
        # This Entity has expired; remove it automatically
        self.remove(entity_id)
        continue
      if latest_time and entity.time_start > latest_time:
        continue
      if earliest_time and entity.time_end < earliest_time:
        continue
      result.append(entity)
    return result

  def upsert(self, entity_ref):
    existed_previously = self.remove(entity_ref.id)
    self._entities_by_id[entity_ref.id] = entity_ref
    for cell_id in entity_ref.cell_ids:
      self._ids_by_cell_id[str(cell_id)].add(entity_ref.id)
    return not existed_previously

  def remove(self, entity_id):
    if entity_id not in self._entities_by_id:
      return False
    entity = self._entities_by_id.pop(entity_id)
    for cell_id in entity.cell_ids:
      cell_id_str = str(cell_id)
      self._ids_by_cell_id[cell_id_str].remove(entity.id)
      if not self._ids_by_cell_id[cell_id_str]:
        del self._ids_by_cell_id[cell_id_str]
    return True

  def get(self, entity_id):
    return self._entities_by_id.get(entity_id, None)

  def exists(self, entity_id):
    return entity_id in self._entities_by_id


class PseudoDatabase(object):
  def __init__(self):
    self.lock = threading.Lock()
    self.identification_service_areas = EntityCollection()
    self.subscriptions = EntityCollection()

db = PseudoDatabase()


def s2_cells_from_polygon(lats, lngs):
  a = s2sphere.LatLng.from_degrees(min(lats), min(lngs))
  b = s2sphere.LatLng.from_degrees(max(lats), max(lngs))
  rect = s2sphere.LatLngRect.from_point_pair(a, b) #TODO: Use true polygon from Google S2 library
  r = s2sphere.RegionCoverer()
  r.min_level = 13
  r.max_level = 13
  r.max_cells = 1000
  cell_ids = r.get_covering(rect)
  return cell_ids


def parse_geo_polygon_string(geo_polygon_string):
  if geo_polygon_string is None:
    raise ValueError('GeoPolygonString is missing')
  coords = geo_polygon_string.split(',')
  if len(coords) % 2 > 0:
    raise ValueError('GeoPolygonString must contain an even number of values; found %d' % len(coords))
  lats = [float(coords[i]) for i in range(0, len(coords), 2)]
  lngs = [float(coords[i]) for i in range(1, len(coords), 2)]
  if len(lats) < 3:
    raise ValueError('GeoPolygonString must contain at least 3 points; only found %d' % len(lats))
  return s2_cells_from_polygon(lats, lngs)


def isa_to_json(entity_ref):
  return {
    'id': entity_ref.id,
    'flights_url': entity_ref.data['flights_url'],
    'owner': entity_ref.data['owner'],
    'time_start': entity_ref.time_start.isoformat(),
    'time_end': entity_ref.time_end.isoformat(),
    'version': entity_ref.data['version']
  }


def subscription_to_json(entity_ref):
  return {
    'id': entity_ref.id,
    'callbacks': entity_ref.data['callbacks'],
    'owner': entity_ref.data['owner'],
    'notification_index': entity_ref.data['notification_index'],
    'time_start': entity_ref.time_end.isoformat(),
    'time_end': entity_ref.time_start.isoformat(),
    'version': entity_ref.data['version']
  }


def get_affected_subscribers(entity_ref):
  affected_subscriptions = db.subscriptions.list_from_cells(
    entity_ref.cell_ids, entity_ref.time_start, entity_ref.time_end)

  for subscription in affected_subscriptions:
    data = subscription.data
    data['notification_index'] += 1
    subscription = EntityReference(
      subscription.id, data, subscription.cell_ids, subscription.time_start, subscription.time_end)
    db.subscriptions.upsert(subscription)

  subscribers_by_url = collections.defaultdict(list)
  for subscription in affected_subscriptions:
    url = subscription.data.get('callbacks', {}).get('identification_service_area_url', None)
    if not url:
      continue
    subscribers_by_url[url].append({
      'subscription_id': subscription.id,
      'notification_index': subscription.data['notification_index']
    })
  return [{'url': url, 'subscriptions': states} for url, states in subscribers_by_url.items()]


def cell_id_str(cell_id):
  s = str(cell_id)[len('CellId: '):]
  while s[-1] == '0':
    s = s[0:-1]
  return s


def error_response(code, message):
  return jsonify({'message': message}), code


class ParseError(RuntimeError):
  def __init__(self, code, message):
    self.code = code
    self.message = message
    super(ParseError, self).__init__()


def parse_extents(request_body):
  now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

  if 'extents' not in request_body:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Missing extents parameter in request body')
  extents = request_body['extents']
  
  if 'time_start' not in extents:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Missing time_start in extents')
  try:
    time_start = iso8601.parse_date(extents['time_start'])
  except iso8601.ParseError as e:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Could not parse extents.time_start: ' + str(e))
  if time_start < now:
    time_start = now
  
  if 'time_end' not in extents:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Missing time_end in extents')
  try:
    time_end = iso8601.parse_date(extents['time_end'])
  except iso8601.ParseError as e:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Could not parse extents.time_end: ' + str(e))
  if time_end < now:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Attempted to create Identification Service Area wholly in the past')

  if time_start > time_end:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'time_start must be before time_end')

  if 'spatial_volume' not in extents:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Missing spatial_volume in extents')
  if 'footprint' not in extents['spatial_volume']:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Missing footprint in extents.spatial_volume')
  if 'vertices' not in extents['spatial_volume']['footprint']:
    raise ParseError(status.HTTP_400_BAD_REQUEST, 'Missing vertices in extents.spatial_volume.footprint')
  vertices = extents['spatial_volume']['footprint']['vertices']
  cell_ids = s2_cells_from_polygon(*zip(*[(vertex['lat'], vertex['lng']) for vertex in vertices]))
  
  return time_start, time_end, cell_ids


def make_version():
  characters = 'abcdefghijklmnopqrstuvwxyz0123456789'
  return ''.join(characters[random.randint(0, len(characters) - 1)] for _ in range(10))


######################################################################
################    WEB SERVICE ENDPOINTS    #########################
######################################################################

@webapp.route('/', methods=['GET'])
@webapp.route('/status', methods=['GET'])
def Status():
  # just a quick status checker, not really a health check
  log.debug('Status handler instantiated...')
  return jsonify({'status': 'success',
                  'message': 'OK',
                  'version': VERSION})


@webapp.route('/v1/dss/identification_service_areas', methods=['GET'])
def SearchIdentificationServiceAreasHandler():
  earliest_time_string = request.args.get('earliest_time', None)
  if not earliest_time_string:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing earliest_time parameter')
  try:
    earliest_time = iso8601.parse_date(earliest_time_string)
  except iso8601.ParseError as e:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Could not parse earliest_time: ' + str(e))

  latest_time_string = request.args.get('latest_time', None)
  if not latest_time_string:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing latest_time parameter')
  try:
    latest_time = iso8601.parse_date(latest_time_string)
  except iso8601.ParseError as e:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Could not parse latest_time: ' + str(e))

  try:
    cell_ids = parse_geo_polygon_string(request.args.get('area', None))
  except ValueError as e:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Invalid area parameter: ' + str(e))

  try:
    uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.read.identification_service_areas')
  except authorization.AuthorizationError as e:
    return error_response(e.code, e.message)

  with db.lock:
    isas = db.identification_service_areas.list_from_cells(cell_ids, earliest_time, latest_time)

  response_body = {
    'service_areas': [isa_to_json(isa) for isa in isas],
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/identification_service_areas/<id>', methods=['GET'])
def GetIdentificationServiceAreaHandler(id):
  with db.lock:
    entity_ref = db.identification_service_areas.get(id)
    cell_ids = entity_ref.cell_ids if entity_ref else None
    try:
      uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.write.identification_service_areas')
    except authorization.AuthorizationError as e:
      return error_response(e.code, e.message)
    if entity_ref is None:
      return error_response(status.HTTP_404_NOT_FOUND, 'No Identification Service Area found with id ' + id)

  response_body = {
    'service_area': isa_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/identification_service_areas/<id>', methods=['PUT'])
def CreateIdentificationServiceAreaHandler(id):
  request_body = request.json

  try:
    time_start, time_end, cell_ids = parse_extents(request_body)
  except ParseError as e:
    return error_response(e.code, e.message)

  if 'flights_url' not in request_body:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing flights_url in request body')
  flights_url = request_body['flights_url']

  try:
    uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.write.identification_service_areas')
  except authorization.AuthorizationError as e:
    return error_response(e.code, e.message)

  data = {
    'owner': uss_id,
    'flights_url': flights_url,
    'version': make_version()
  }

  entity_ref = EntityReference(id, data, cell_ids, time_start, time_end)

  with db.lock:
    if db.identification_service_areas.exists(id):
      return error_response(status.HTTP_409_CONFLICT, 'Identification Service Area already exists with ID ' + id)
    db.identification_service_areas.upsert(entity_ref)
    subscribers = get_affected_subscribers(entity_ref)

  response_body = {
    'subscribers': subscribers,
    'service_area': isa_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/identification_service_areas/<id>/<version>', methods=['PUT'])
def UpdateIdentificationServiceAreaHandler(id, version):
  request_body = request.json

  try:
    time_start, time_end, cell_ids = parse_extents(request_body)
  except ParseError as e:
    return error_response(e.code, e.message)

  if 'flights_url' not in request_body:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing flights_url in request body')
  flights_url = request_body['flights_url']

  try:
    uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.write.identification_service_areas')
  except authorization.AuthorizationError as e:
    return error_response(e.code, e.message)

  data = {
    'owner': uss_id,
    'flights_url': flights_url,
    'version': make_version()
  }

  entity_ref = EntityReference(id, data, cell_ids, time_start, time_end)

  with db.lock:
    old_entity_ref = db.identification_service_areas.get(id)
    if old_entity_ref is None:
      return error_response(status.HTTP_404_NOT_FOUND, 'No Identification Service Area found with id ' + id)
    if old_entity_ref.data.get('version', None) != version:
      message = ('Provided version %s does not match pre-existing Identification Service Area version ' +
                 old_entity_ref.data.get('version', '<missing>'))
      return error_response(status.HTTP_409_CONFLICT, message)
    db.identification_service_areas.upsert(entity_ref)
    subscribers = get_affected_subscribers(entity_ref)

  response_body = {
    'subscribers': subscribers,
    'service_area': isa_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id,
              'old_version': old_entity_ref.data.get('version', '<missing>') if old_entity_ref else '<does not exist>'}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/identification_service_areas/<id>/<version>', methods=['DELETE'])
def DeleteIdentificationServiceAreaHandler(id, version):
  with db.lock:
    entity_ref = db.identification_service_areas.get(id)
    cell_ids = entity_ref.cell_ids if entity_ref else None
    try:
      uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.write.identification_service_areas')
    except authorization.AuthorizationError as e:
      return error_response(e.code, e.message)
    if entity_ref is None:
      return error_response(status.HTTP_404_NOT_FOUND, 'No Identification Service Area found with id ' + id)
    if entity_ref.data.get('version', None) != version:
      message = ('Provided version %s does not match pre-existing Identification Service Area version ' +
                 entity_ref.data.get('version', '<missing>'))
      return error_response(status.HTTP_409_CONFLICT, message)
    db.identification_service_areas.remove(id)
    subscribers = get_affected_subscribers(entity_ref)

  response_body = {
    'subscribers': subscribers,
    'service_area': isa_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/subscriptions', methods=['GET'])
def GetSubscriptionsHandler():
  try:
    cell_ids = parse_geo_polygon_string(request.args.get('area', None))
  except ValueError as e:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Invalid area parameter: ' + str(e))

  try:
    uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.read.identification_service_areas')
  except authorization.AuthorizationError as e:
    return error_response(e.code, e.message)

  with db.lock:
    subscriptions = db.subscriptions.list_from_cells(cell_ids)

  subscriptions = [subscription for subscription in subscriptions if subscription.data['owner'] == uss_id]

  response_body = {
    'subscriptions': [subscription_to_json(subscription) for subscription in subscriptions],
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/subscriptions/<id>', methods=['GET'])
def GetSubscriptionHandler(id):
  with db.lock:
    entity_ref = db.subscriptions.get(id)
    cell_ids = entity_ref.cell_ids if entity_ref else None
    try:
      uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.read.identification_service_areas')
    except authorization.AuthorizationError as e:
      return error_response(e.code, e.message)
    if entity_ref is None:
      return error_response(status.HTTP_404_NOT_FOUND, 'No Subscription found with id ' + id)

  response_body = {
    'subscription': subscription_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/subscriptions/<id>', methods=['PUT'])
def CreateSubscriptionHandler(id):
  request_body = request.json

  try:
    time_start, time_end, cell_ids = parse_extents(request_body)
  except ParseError as e:
    return error_response(e.code, e.message)

  if 'callbacks' not in request_body:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing callbacks in request body')
  callbacks = request_body['callbacks']
  if 'identification_service_area_url' not in callbacks:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing identification_service_area_url in callbacks')

  try:
    uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.read.identification_service_areas')
  except authorization.AuthorizationError as e:
    return error_response(e.code, e.message)

  data = {
    'owner': uss_id,
    'callbacks': callbacks,
    'notification_index': 0,
    'version': make_version()
  }

  entity_ref = EntityReference(id, data, cell_ids, time_start, time_end)

  with db.lock:
    if db.subscriptions.exists(id):
      return error_response(status.HTTP_409_CONFLICT, 'Subscription already exists with ID ' + id)
    db.subscriptions.upsert(entity_ref)
    isas = db.identification_service_areas.list_from_cells(cell_ids, time_start, time_end)

  response_body = {
    'service_areas': [isa_to_json(isa) for isa in isas],
    'subscription': subscription_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/subscriptions/<id>/<version>', methods=['PUT'])
def UpdateSubscriptionHandler(id, version):
  request_body = request.json

  try:
    time_start, time_end, cell_ids = parse_extents(request_body)
  except ParseError as e:
    return error_response(e.code, e.message)

  if 'callbacks' not in request_body:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing callbacks in request body')
  callbacks = request_body['callbacks']
  if 'identification_service_area_url' not in callbacks:
    return error_response(status.HTTP_400_BAD_REQUEST, 'Missing identification_service_area_url in callbacks')

  try:
    uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.read.identification_service_areas')
  except authorization.AuthorizationError as e:
    return error_response(e.code, e.message)

  data = {
    'owner': uss_id,
    'callbacks': callbacks,
    'notification_index': 0,  # Updated below
    'version': make_version()
  }

  entity_ref = EntityReference(id, data, cell_ids, time_start, time_end)

  with db.lock:
    old_entity_ref = db.subscriptions.get(id)
    if old_entity_ref is None:
      return error_response(status.HTTP_404_NOT_FOUND, 'No Subscription found with id ' + id)
    if old_entity_ref.data.get('version', None) != version:
      message = ('Provided version %s does not match pre-existing Subscription version ' +
                 old_entity_ref.data.get('version', '<missing>'))
      return error_response(status.HTTP_409_CONFLICT, message)
    db.subscriptions.upsert(entity_ref)
    isas = db.identification_service_areas.list_from_cells(cell_ids, time_start, time_end)

  response_body = {
    'service_areas': [isa_to_json(isa) for isa in isas],
    'subscription': subscription_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


@webapp.route('/v1/dss/subscriptions/<id>/<version>', methods=['DELETE'])
def DeleteSubscriptionHandler(id, version):
  with db.lock:
    entity_ref = db.subscriptions.get(id)
    cell_ids = entity_ref.cell_ids if entity_ref else None
    try:
      uss_id = auth.ValidateAccessToken(request.headers, cell_ids, 'dss.read.identification_service_areas')
    except authorization.AuthorizationError as e:
      return error_response(e.code, e.message)
    if entity_ref is None:
      return error_response(status.HTTP_404_NOT_FOUND, 'No Subscription found with id ' + id)
    if entity_ref.data.get('version', None) != version:
      message = ('Provided version %s does not match pre-existing Subscription version ' +
                 entity_ref.data.get('version', '<missing>'))
      return error_response(status.HTTP_409_CONFLICT, message)
    db.subscriptions.remove(id)

  response_body = {
    'subscription': subscription_to_json(entity_ref),
    'debug': {'cell_ids': [cell_id_str(cell_id) for cell_id in cell_ids],
              'uss_id': uss_id}
  }

  return jsonify(response_body)


def ParseOptions(argv):
  """Parses desired options from the command line.

  Uses the command line parameters as argv, which can be altered as needed for
  testing.

  Args:
    argv: Command line parameters
  Returns:
    Options structure
  """
  parser = OptionParser(
      usage='usage: %prog [options]', version='%prog ' + VERSION)
  parser.add_option(
      '-s',
      '--server',
      dest='server',
      default=os.getenv('INTERUSS_API_SERVER', '127.0.0.1'),
      help='Specific server name to use on this machine for the web services '
      '[or env variable INTERUSS_API_SERVER]',
      metavar='SERVER')
  parser.add_option(
      '-p',
      '--port',
      dest='port',
      default=int(os.getenv('INTERUSS_API_PORT', '5000')),
      help='Specific port to use on this machine for the web services '
      '[or env variable INTERUSS_API_PORT]',
      metavar='PORT')
  parser.add_option(
      '-v',
      '--verbose',
      action='store_true',
      dest='verbose',
      default=(os.environ.get('INTERUSS_VERBOSE', 'false').lower() == 'true'),
      help='Verbose (DEBUG) logging [or env variable INTERUSS_VERBOSE]')
  parser.add_option(
      '-t',
      '--testid',
      dest='testid',
      default=os.environ.get('INTERUSS_TESTID'),
      help='Force testing mode with test data located in specific test id  '
      '[or env variable INTERUSS_TESTID]',
      metavar='TESTID')
  parser.add_option(
      '-k',
      '--public_key',
      dest='public_key',
      default=os.environ.get('INTERUSS_PUBLIC_KEY'),
      help='Public key of global authorization authority [or env variable '
      'INTERUSS_PUBLIC_KEY]',
      metavar='RSAKEY')
  parser.add_option(
      '-a',
      '--auth_config',
      dest='auth_config',
      default=os.environ.get('INTERUSS_AUTH_CONFIG'),
      help='JSON describing authorization configuration, or path to JSON '
      'resource [or env variable INTERUSS_AUTH_CONFIG]',
      metavar='CONFIG')
  (options, args) = parser.parse_args(argv)
  del args
  return options


def InitializeConnection(options):
  """Initializes the wrapper and the connection to the zookeeper servers.

  The side effects of this method are to set the global variable 'wrapper' and
  call authorization.set_test_id if appropriate.

  Args:
    options: Options structure with a field per option.
  """
  global wrapper, auth

  if not options.public_key and not options.auth_config:
    log.error('Public key or auth config must be provided.')
    sys.exit(-1)

  if options.verbose:
    log.setLevel(logging.DEBUG)
  auth = authorization.Authorizer(options.public_key, options.auth_config)
  if options.testid:
    auth.SetTestId(options.testid)


@webapp.before_first_request
def BeforeFirstRequest():
  if auth is None:
    InitializeConnection(ParseOptions([]))


def main(argv):
  log.debug(
      """Instantiated application, parsing commandline
    %s and initializing connection...""", str(argv))
  options = ParseOptions(argv)
  InitializeConnection(options)
  log.info('Starting webserver...')
  webapp.run(host=options.server, port=int(options.port))


# this is what starts everything when run directly as an executable
if __name__ == '__main__':
  main(sys.argv)
