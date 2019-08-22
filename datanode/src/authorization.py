"""The InterUSS Platform Data Node authorization tools.

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

import abc
import json
import logging
import numbers
import flask
import jwt
import requests
from rest_framework import status
from shapely.geometry import Polygon
import s2sphere


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('InterUSS_DataNode_Authorization')


class AuthorizationError(RuntimeError):
  def __init__(self, code, message):
    self.code = code
    self.message = message
    super(AuthorizationError, self).__init__()


def JoinZoom(zoom, tiles):
  """Combine single zoom and multiple tiles into tile triplets."""
  return ((zoom, t[0], t[1]) for t in tiles)


class Authorizer(object):
  """Manages authorization on a per-area basis."""

  def __init__(self, public_key, auth_config_string):
    self.test_id = None
    self.authorities = []
    self._cache = {}

    if public_key:
      log.info('Using global auth provider from single public key')
      self.authorities.append(
        _AuthorizationAuthority(public_key, 'Global authority'))

    if auth_config_string:
      self.authorities.extend(_ParseAuthorities(auth_config_string))

  def SetTestId(self, testid):
    self.test_id = testid
    log.info('Authorization set to test mode with test ID=%s' % self.test_id)

  def ValidateAccessToken(self, headers, cell_ids, required_scope):
    """Checks the access token, aborting if it does not pass.

    Uses one or more OAuth public keys to validate an access token.

    Args:
      headers: dict of headers from flask.request
      tiles: collection of (zoom, x,y) slippy tiles user is attempting to access

    Returns:
      USS identification from OAuth client_id or sub field

    Raises:
      HTTPException: when the access token is invalid or inappropriate
    """
    uss_id = None
    if self.test_id:
      if self.test_id in headers.get('Authorization', ''):
        return headers['Authorization']
      elif 'Authorization' not in headers:
        return self.test_id

    # TODO(hikevin): Replace with OAuth Discovery and JKWS
    token = headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
      log.error('Attempt to access resource without Bearer token in Authorization header.')
      raise AuthorizationError(status.HTTP_403_FORBIDDEN,
                  'Valid JWT access token must be provided in Authorization header.')

    # Verify validity of claims without checking signature
    try:
      r = jwt.decode(token, algorithms='RS256', verify=False)
      uss_id = r['client_id'] if 'client_id' in r else r.get('sub', None)
      if required_scope not in r.get('scope', ''):
        raise AuthorizationError(status.HTTP_403_FORBIDDEN,
                    'Access token missing required scope %s; found %s' %
                    (required_scope, r.get('scope', '<no scope claim>')))
    except jwt.ImmatureSignatureError:
      log.error('Access token is immature.')
      raise AuthorizationError(status.HTTP_401_UNAUTHORIZED,
                  'OAuth access_token is invalid: token is immature.')
    except jwt.ExpiredSignatureError:
      log.error('Access token has expired.')
      raise AuthorizationError(status.HTTP_401_UNAUTHORIZED,
                  'OAuth access_token is invalid: token has expired.')
    except jwt.DecodeError:
      log.error('Access token is invalid and cannot be decoded.')
      raise AuthorizationError(status.HTTP_400_BAD_REQUEST,
                  'OAuth access_token is invalid: token cannot be decoded.')
    except jwt.InvalidTokenError as e:
      log.error('Unexpected InvalidTokenError: %s', str(e))
      raise AuthorizationError(status.HTTP_500_INTERNAL_SERVER_ERROR,
                  'Unexpected token error: ' + str(e))
    issuer = r.get('iss', None)

    if cell_ids:
      # Check only authorities that manage all specified cells
      authorities = set.intersection(
          *[self._GetAuthorities(issuer, cell_id) for cell_id in cell_ids])
    else:
      authorities = self._GetAuthorities(issuer, None)
    if not authorities:
      raise AuthorizationError(status.HTTP_401_UNAUTHORIZED,
                  'No authorization authorities could be found')

    # Check signature against all possible public keys
    valid = False
    for authority in authorities:
      try:
        if 'aud' in r:
          # Accept any audience for debugging; TODO: fix
          jwt.decode(token, authority.public_key, algorithms='RS256', audience=r['aud'])
        else:
          jwt.decode(token, authority.public_key, algorithms='RS256')
        valid = True
        break
      except jwt.InvalidSignatureError:
        # Access token signature not valid for this public key, but might be
        # valid for a different public key.
        pass
      except jwt.ExpiredSignatureError:
        log.error('Access token has expired.')
        raise AuthorizationError(status.HTTP_401_UNAUTHORIZED,
                    'OAuth access_token is invalid: token has expired.')
    if not valid:
      # Check against all authorities
      for authority in self.authorities:
        try:
          if 'aud' in r:
            # Accept any audience for debugging; TODO: fix
            jwt.decode(token, authority.public_key, algorithms='RS256', audience=r['aud'])
          else:
            jwt.decode(token, authority.public_key, algorithms='RS256')
          invalid_cell = None
          if cell_ids:
            for cell_id in cell_ids:
              if not authority.is_applicable(issuer, cell_id):
                invalid_cell = cell_id
                break
          if invalid_cell:
            raise AuthorizationError(
                status.HTTP_401_UNAUTHORIZED,
                'Access token has valid signature but "%s" is not applicable to %s' %
                (authority.name, str(invalid_cell)))
          else:
            raise AuthorizationError(status.HTTP_401_UNAUTHORIZED,
                        'Access token has valid signature but does not match '
                        'server\'s authority configuration')
        except jwt.InvalidSignatureError:
          # Token signature isn't valid for this authority
          pass
        except jwt.ExpiredSignatureError:
          log.error('Access token has expired.')
          raise AuthorizationError(status.HTTP_401_UNAUTHORIZED,
                                   'OAuth access_token is invalid: token has expired.')

      raise AuthorizationError(status.HTTP_401_UNAUTHORIZED,
                  'Access token signature is invalid')

    return uss_id

  def _GetAuthorities(self, issuer, cell_id):
    """Retrieve set of applicable AuthorizationAuthorities."""
    cache_key = (issuer, cell_id)
    if cache_key not in self._cache:
      self._cache[cache_key] = set(a for a in self.authorities
                                   if a.is_applicable(issuer, cell_id))
    return self._cache[cache_key]


class _AuthorizationAuthority(object):
  """Authority that grants access tokens to access part of this data node."""

  def __init__(self, public_key, name):
    public_key = parse_string_source(public_key)

    # ENV variables sometimes don't pass newlines, spec says white space
    # doesn't matter, but pyjwt cares about it, so fix it
    public_key = public_key.replace(' PUBLIC ', '_PLACEHOLDER_')
    public_key = public_key.replace(' ', '\n')
    public_key = public_key.replace('_PLACEHOLDER_', ' PUBLIC ')
    self.public_key = public_key
    self.constraints = []
    self.name = name

  def is_applicable(self, issuer, tile):
    """Determine whether an AuthorizationAuthority is applicable for tile.

    Args:
      issuer: Content of access token's `iss` JWT field.
      tile: Slippy (zoom, x, y) for tile of interest.

    Returns:
      True if this AuthorizationAuthority is applicable for the specified tile.
    """
    if self.constraints:
      return all(c.is_applicable(issuer, tile) for c in self.constraints)
    else:
      return True


class _AuthorizationConstraint(object):
  """Base class for constraints on when an AuthorizationAuthority applies."""
  __metaclass__ = abc.ABCMeta

  @abc.abstractmethod
  def is_applicable(self, issuer, cell_id):
    """Determine whether an AuthorizationAuthority is applicable for an S2 cell.

    Args:
      issuer: Content of access token's `iss` JWT field.
      cell_id: Integer S2 cell of interest.

    Returns:
      True if the associated AuthorizationAuthority is applicable for the
      specified cell.
    """
    raise NotImplementedError('Abstract method is_applicable not implemented')


class _IssuerConstraint(_AuthorizationConstraint):
  """Access token `iss` field must match issuer."""

  def __init__(self, issuer):
    self._issuer = issuer

  def is_applicable(self, issuer, cell_id):
    # Overrides method in parent class.
    return issuer == self._issuer


class _AreaConstraint(_AuthorizationConstraint):
  """Tiles must lie in or out of an arbitrary geo polygon."""

  def __init__(self, points, inside):
    self._polygon = Polygon(points)
    self._inside = inside
    raise NotImplementedError('AreaConstraints not yet supported')

  def is_applicable(self, issuer, cell_id):
    # Overrides method in parent class.
    if not cell_id:
      return True
    raise NotImplementedError('AreaConstraints not yet supported')


class _RangeConstraint(_AuthorizationConstraint):
  """Cells must lie inside one of an explicit list of cells."""

  def __init__(self, cell_ids, inclusive):
    self._cells = s2sphere.CellUnion([_GetCellId(cell_id) for cell_id in cell_ids])
    self._inclusive = inclusive

  def is_applicable(self, issuer, cell_id):
    # Overrides method in parent class.
    if not cell_id:
      return True
    intersects = s2sphere.CellUnion([cell_id]).intersects(self._cells)
    return intersects if self._inclusive else not intersects


def _GetCellId(cell_id):
  """Convert a JSON cell ID into an S2 cell.

  Args:
    cell_id: Decoded JSON structure describing cell.
      Number: Decimal S2 cell ID
      String: Hexadecimal S2 cell ID

  Returns:
    S2 cell for cell_id.
  """
  if isinstance(cell_id, numbers.Number):
    return s2sphere.CellId(cell_id)
  elif isinstance(cell_id, basestring):
    return s2sphere.CellId(int(cell_id + ''.join('0' for _ in range(16 - len(cell_id))), 16))
  raise ValueError('Invalid range_spec')


def _ParseAuthorities(config_string):
  """Create a list of AuthorizationAuthorities based on JSON configuration.

  Example JSON:
  [{"public_key": "-----BEGIN PUBLIC KEY----- ..."},
   {"name": "Specific area authority",
    "public_key": "-----BEGIN PUBLIC KEY----- ...",
    "constraints": [{
      "type": "issuer",
      "issuer": "gov.area.authority"}, {
      "type": "area",
      "outline": [[30.064,-99.147],[30.054,-99.147],[30.054,-99.134],[30.064,-99.134]],

  Also see authorization_test.py.

  Args:
    config_string: Configuration description of authorization authorities.
      If a resource URL (file|http|https://), first load content from URL.
      Interpreted as JSON per examples.

  Returns:
    List of AuthorizationAuthorities described in provided config.
  """
  print('Original config string:')
  print(config_string)
  config_string = parse_string_source(config_string)
  print('Parsing auth authorities:')
  print(config_string)

  authority_specs = json.loads(config_string)
  authorities = []
  for i, authority_spec in enumerate(authority_specs):
    authority = _AuthorizationAuthority(
      authority_spec['public_key'],
      authority_spec.get('name', 'Authority %d' % i))
    if 'constraints' in authority_spec:
      for constraint_spec in authority_spec['constraints']:
        if constraint_spec['type'] == 'issuer':
          constraint = _IssuerConstraint(constraint_spec['issuer'])
        elif constraint_spec['type'] == 'area':
          constraint = _AreaConstraint(
            constraint_spec['outline'], constraint_spec.get('inside', True))
        elif constraint_spec['type'] == 'range':
          constraint = _RangeConstraint(
            constraint_spec['cell_ids'], constraint_spec.get('inclusive', True))
        else:
          raise ValueError('Invalid constraint type: ' +
                           constraint_spec.get('type', '<not specified>'))
        authority.constraints.append(constraint)
    authorities.append(authority)
  return authorities


def parse_string_source(s):
  if s.startswith('file://'):
    with open(s[len('file://'):], 'r') as f:
      s = f.read()
  if (s.startswith('http://') or
    s.startswith('https://')):
    req = requests.get(s)
    s = req.content
  return s
