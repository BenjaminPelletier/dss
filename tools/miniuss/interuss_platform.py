"""Tools for interacting with the InterUSS Platform.

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

import base64
import collections
import copy
import datetime
import json
import logging
import sys

import requests
from shapely import geometry

import formatting


log = logging.getLogger('InterUSSPlatform')

EXPIRATION_BUFFER = 5  # seconds

# Access token scope for accessing the InterUSS Platform.
INTERUSS_SCOPE = 'utm.nasa.gov_write.conflictmanagement'

# Access token scope for writing UVRs to the InterUSS Platform.
UVR_SCOPE = 'utm.nasa.gov_write.constraint'

Coord = collections.namedtuple('Coord', 'lat lng')


def _aggregate_timestamps(timestamps, aggregator):
  result = None
  for t in timestamps:
    timestamp = formatting.parse_timestamp(t)
    result = timestamp if result is None else aggregator(result, timestamp)
  return result


def _tcl4_operations_to_interuss(operations):
  for operation in operations:
    min_timestamp = _aggregate_timestamps(
      (v['effective_time_begin'] for v in operation['operation_volumes']), min)
    max_timestamp = _aggregate_timestamps(
      (v['effective_time_end'] for v in operation['operation_volumes']), max)
    yield {
      'gufi': operation['gufi'],
      'operation_signature': 'n/a',
      'effective_time_begin': formatting.timestamp(min_timestamp),
      'effective_time_end': formatting.timestamp(max_timestamp)
    }


def _boundary_of_operations(operations):
  points = []
  for operation in operations:
    for volume in operation['operation_volumes']:
      for lng, lat in volume['operation_geography']['coordinates'][0]:
        points.append((lng, lat))
  hull = geometry.polygon.orient(
    geometry.MultiPoint(points).convex_hull)
  x, y = hull.exterior.coords.xy
  return [Coord(lat, lng) for lng, lat in zip(x, y)]


class Client(object):
  """Client wrapper around interactions with an InterUSS Platform server."""

  def __init__(self, base_url, zoom, auth_url, username, password, uss_baseurl):
    """Instantiate a client to communicate with an InterUSS Platform server.

    Args:
      base_url: URL of InterUSS Platform server, without any verbs.
      zoom: Integer zoom level in which operations are being coordinated.
      auth_url: URL to POST to with credentials to obtain access token.
      username: Basic authorization username to obtain access token.
      password: Basic authorization password to obtain access token.
      uss_baseurl: URL prefix for this USS's USS endpoints.
    """
    self._base_url = base_url
    self._zoom = zoom
    self._username = username
    self.uss_baseurl = uss_baseurl

    self._token_manager = TokenManager(auth_url, username=username, password=password)

    self._op_area = None

  def get_operators(self, intended_operations):
    """Retrieve USSs with potentially-intersecting operations.

    Args:
      intended_operations: TCL4 Operations from which the area of interest
        should be extracted.

    Returns:
      operators: List of TCL4 Operators in area of interest.
      uvrs: List of TCL4 UASVolumeReservations in area of interest.
      sync_token: InterUSS Platform sync token for writing updates.
    """
    return self.get_operators_by_area(_boundary_of_operations(intended_operations))

  def get_operators_by_area(self, area):
    """Retrieve USS information for a specific area.

    Args:
      area: List of Coords describing the outline of the area of interest.

    Returns:
      operators: List of TCL4 Operators in area of interest.
      uvrs: List of TCL4 UASVolumeReservations in area of interest.
      sync_token: InterUSS Platform sync token for writing updates.
    """
    coords = ','.join('%.6f,%.6f' % (p.lat, p.lng) for p in area)
    response = requests.get(
      url=self._base_url + '/GridCellsOperator/%d' % self._zoom,
      headers=self.get_header(INTERUSS_SCOPE),
      params={
        'coords': coords,
        'coord_type': 'polygon',
      })
    response.raise_for_status()
    response_json = json.loads(response.content)
    sync_token = response_json['sync_token']
    operators = response_json['data']['operators']
    uvrs = response_json['data']['uvrs']
    return operators, uvrs, sync_token

  def get_operators_by_cell(self, slippy_cell):
    """Retrieve USSs in a specific Slippy cell.

    Args:
      slippy_cell: Slippy cell path; e.g., '10/282/397'

    Returns:
      operators: List of TCL4 Operators in area of interest.
      uvrs: List of TCL4 UASVolumeReservations in area of interest.
      sync_token: InterUSS Platform sync token for writing updates.
    """
    response = requests.get(
      url=self._base_url + '/GridCellOperator/%s' % slippy_cell,
      headers=self.get_header(INTERUSS_SCOPE))
    response.raise_for_status()
    response_json = json.loads(response.content)
    sync_token = response_json['sync_token']
    operators = response_json['data']['operators']
    uvrs = response_json['data']['uvrs']
    return operators, uvrs, sync_token

  def upsert_operator(self, operations, min_time=None, max_time=None):
    """Inform the InterUSS Platform of intended operations from this USS.

    Args:
      operations: List of TCL4 Operations that operator is currently managing.
      min_time: Python datetime for minimum_operation_timestamp in operator entry, if beyond operations.
      max_time: Python datetime for maximum_operation_timestamp in operator entry, if beyond operations.
    """
    if self._op_area is not None:
      self.remove_operator()
    if not operations:
      return

    _, _, sync_token = self.get_operators(operations)
    area = _boundary_of_operations(operations)
    interuss_operations = list(_tcl4_operations_to_interuss(operations))
    min_timestamp = _aggregate_timestamps(
      (op['effective_time_begin'] for op in interuss_operations), min)
    if min_time and min_time < min_timestamp:
      min_timestamp = min_time
    max_timestamp = _aggregate_timestamps(
      (op['effective_time_end'] for op in interuss_operations), max)
    if max_time and max_time > max_timestamp:
      max_timestamp = max_time
    coords = ','.join('%.6f,%.6f' % (p.lat, p.lng) for p in area)
    log.info('upsert_operator coords are ' + coords)
    response = requests.put(
      url=self._base_url + '/GridCellsOperator/%d' % self._zoom,
      headers=self.get_header(INTERUSS_SCOPE),
      json={
        'sync_token': sync_token,
        'coords': coords,
        'coord_type': 'polygon',
        'uss_baseurl': self.uss_baseurl,
        'minimum_operation_timestamp': formatting.timestamp(min_timestamp),
        'maximum_operation_timestamp': formatting.timestamp(max_timestamp),
        'announcement_level': 'ALL',
        'operations': interuss_operations
      })
    response.raise_for_status()
    self._op_area = area

  def insert_observer(self, slippy_cell, min_time, max_time):
    """If no operator entry is present in slippy_cell, add one without operations.

    Args:
      slippy_cell: Slippy cell path; e.g., '10/282/397'
      min_time: Python datetime for minimum_operation_timestamp in operator entry.
      max_time: Python datetime for maximum_operation_timestamp in operator entry.
    """
    operators, _, sync_token = self.get_operators_by_cell(slippy_cell)
    if not any(True for op in operators if op['uss'] == self._username):
      log.info('Adding observer entry to cell %s', slippy_cell)
      response = requests.put(
        url=self._base_url + '/GridCellOperator/' + slippy_cell,
        headers=self.get_header(INTERUSS_SCOPE),
        json={
          'sync_token': sync_token,
          'uss_baseurl': self.uss_baseurl,
          'minimum_operation_timestamp': formatting.timestamp(min_time),
          'maximum_operation_timestamp': formatting.timestamp(max_time),
          'announcement_level': 'ALL',
          'operations': []
        })
      log.debug('@@@ About to raise for status')
      response.raise_for_status()
      log.debug('@@@ Raised for status')

  def remove_operator(self):
    """Inform the InterUSS Platform that managed operations have ceased."""
    if self._op_area is None:
      raise ValueError('Cannot remove operations when no operations are active')
    coords = ','.join('%.6f,%.6f' % (p.lat, p.lng) for p in self._op_area)
    response = requests.delete(
      url=self._base_url + '/GridCellsOperator/%d' % self._zoom,
      headers=self.get_header(INTERUSS_SCOPE),
      json={
        'coords': coords,
        'coord_type': 'polygon'
      })
    response.raise_for_status()
    self._op_area = None

  def remove_operator_by_cell(self, slippy_cell):
    """Attempt to remove an operator entry for a specific cell.

    Args:
      slippy_cell: Slippy cell path; e.g., '10/282/397'
    """
    response = requests.delete(
      url=self._base_url + '/GridCellOperator/' + slippy_cell,
      headers=self.get_header(INTERUSS_SCOPE))
    return response

  def upsert_uvr(self, uvr):
    """Insert or update a UVR.

    Args:
      uvr: Full UVR data structure.

    Returns:
      UVR, as reported by the InterUSS Platform.
    """
    final_uvr = copy.deepcopy(uvr)
    final_uvr['uss_name'] = self._username
    response = requests.put(
      url=self._base_url + ('/UVR/%d/%s' % (self._zoom, final_uvr['message_id'])),
      headers=self.get_header(UVR_SCOPE),
      json=final_uvr)
    response.raise_for_status()
    return response.json()

  def remove_uvr(self, uvr):
    """Remove a UVR.

    Args:
      uvr: Full UVR data structure.

    Returns:
      The UVR that was removed.
    """
    final_uvr = copy.deepcopy(uvr)
    final_uvr['uss_name'] = self._username
    response = requests.delete(
      url=self._base_url + ('/UVR/%d/%s' % (self._zoom, final_uvr['message_id'])),
      headers=self.get_header(UVR_SCOPE),
      json=final_uvr)
    response.raise_for_status()
    return response.json()

  def get_header(self, scope):
    """Get a header dict containing authorization for the specified scope.

    Args:
      scope: Access token scope desired.

    Returns:
      dict that may be passed to a requests headers parameter.
    """
    return {'Authorization': 'Bearer ' + self._token_manager.get_token(scope)}


CachedToken = collections.namedtuple('CachedToken', ('value', 'expiration'))


class TokenManager(object):
  """Transparently provides access tokens, from cache when possible."""

  def __init__(self, auth_url, auth_key=None, username=None, password=None):
    """Create a TokenManager.

    Args:
      auth_url: URL the provides an access token.
      auth_key: Base64-encoded username and password.
      username: If auth_key is not provided, username from which to construct it.
      password: If auth_key is not provided, password from which to construct it.
    """
    if '&scope=' in auth_url:
      print('USAGE ERROR: The auth URL should now be provided without a scope '
            'specified in its GET parameters.')
      sys.exit(1)

    if not auth_key:
      auth_key = base64.b64encode(username + ':' + password)

    self._auth_url = auth_url
    self._auth_key = auth_key
    self._tokens = {}

  def _retrieve_token(self, scope):
    """Call the specified OAuth server to retrieve an access token.

    Args:
      scope: Access token scope to request.

    Returns:
      CachedToken with requested scope.

    Raises:
      ValueError: When access_token was not returned properly.
    """
    url = self._auth_url + '&scope=' + scope
    r = requests.post(url, headers={'Authorization': 'Basic ' + self._auth_key})
    r.raise_for_status()
    result = r.content
    result_json = json.loads(result)
    if 'access_token' in result_json:
      token = result_json['access_token']
      expires_in = int(result_json.get('expires_in', 0))
      expiration = (datetime.datetime.utcnow() +
                    datetime.timedelta(seconds=expires_in - EXPIRATION_BUFFER))
      return CachedToken(token, expiration)
    else:
      raise ValueError('Error getting token: ' + r.content)

  def get_token(self, scope):
    """Retrieve a current access token with the requested scope.

    Args:
      scope: Access token scope to request.

    Returns:
      Access token content.

    Raises:
      ValueError: When access_token was not returned properly.
    """
    if scope in self._tokens:
      if self._tokens[scope].expiration > datetime.datetime.utcnow():
        return self._tokens[scope].value

    print('')
    print('Getting access token for %s...' % scope)
    self._tokens[scope] = self._retrieve_token(scope)
    return self._tokens[scope].value
