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

import collections
import datetime
import json
import logging

import requests
from shapely import geometry

import formatting


log = logging.getLogger('InterUSSPlatform')

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
    self._auth_url = auth_url
    self._username = username
    self._password = password
    self.uss_baseurl = uss_baseurl

    self._access_token = None
    self._token_expires = None

    self._op_area = None

  def _refresh_access_token(self):
    """Ensure that self._access_token contains a valid access token."""
    if self._access_token and datetime.datetime.utcnow() < self._token_expires:
      return
    log.info('Retrieving new token')
    t0 = datetime.datetime.utcnow()
    response = requests.post(
      url=self._auth_url,
      auth=(self._username, self._password))
    response.raise_for_status()
    r = response.json()
    self._access_token = r['access_token']
    self._token_expires = t0 + datetime.timedelta(seconds=r['expires_in'])

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
    self._refresh_access_token()
    area = _boundary_of_operations(intended_operations)
    coords = ','.join('%.6f,%.6f' % (p.lat, p.lng) for p in area)
    response = requests.get(
      url=self._base_url + '/GridCellsOperator/%d' % self._zoom,
      headers={'Authorization': 'Bearer ' + self._access_token},
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

  def upsert_operator(self, operations):
    """Inform the InterUSS Platform of intended operations from this USS.

    Args:
      operations: List of TCL4 Operations that operator is currently managing.
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
    max_timestamp = _aggregate_timestamps(
      (op['effective_time_end'] for op in interuss_operations), max)
    coords = ','.join('%.6f,%.6f' % (p.lat, p.lng) for p in area)
    response = requests.put(
      url=self._base_url + '/GridCellsOperator/%d' % self._zoom,
      headers={'Authorization': 'Bearer ' + self._access_token},
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

  def remove_operator(self):
    """Inform the InterUSS Platform that managed operations have ceased."""
    if self._op_area is None:
      raise ValueError('Cannot remove operations when no operations are active')
    self._refresh_access_token()
    coords = ','.join('%.6f,%.6f' % (p.lat, p.lng) for p in self._op_area)
    response = requests.delete(
      url=self._base_url + '/GridCellsOperator/%d' % self._zoom,
      headers={'Authorization': 'Bearer ' + self._access_token},
      json={
        'coords': coords,
        'coord_type': 'polygon'
      })
    response.raise_for_status()
    self._op_area = None
