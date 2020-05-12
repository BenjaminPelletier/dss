from datetime import datetime, timezone
import logging
from typing import Dict, Optional, Set
import uuid

from app.dsslib import format_utils
from app.scd import geo


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('Operations')


def make_ovn():
  return str(uuid.uuid4())


class Operation(object):
  """Data structure for an SCD Operation."""

  def __init__(
    self,
    id: uuid.UUID,
    owner: str,
    version: int,
    ovn: str,
    vol4: geo.Volume4,
    uss_base_url: str,
    subscription: uuid.UUID):
    """Create new SCD Operation."""
    self.id = id
    self.owner = owner
    self.version = version
    self.ovn = ovn
    self.vol4 = vol4
    self.uss_base_url = uss_base_url
    self.subscription = subscription

  def to_dict(self, include_ovn: bool):
    result = {
      'id': str(self.id),
      'owner': self.owner,
      'version': self.version,
      'time_start': format_utils.format_ts(self.vol4.time_start),
      'time_end': format_utils.format_ts(self.vol4.time_end),
      'uss_base_url': self.uss_base_url,
      'subscription_id': str(self.subscription)
    }
    if include_ovn:
      result['ovn'] = self.ovn
    return result


def from_request(
    id: str, json: Dict, owner: str, subscription_id: uuid.UUID, existing_operation: Optional[Operation],
    extents: geo.Volume4) -> Operation:
  """Create an SCD Operation from a request structure."""

  # Validate input
  id_uuid = uuid.UUID(id)

  if existing_operation is not None:
    if 'old_version' not in json:
      raise ValueError('Missing `old_version` to update existing Operation')
    elif json['old_version'] != existing_operation.version:
      raise ValueError('`old_version` does not match existing Operation version')
  else:
    if json.get('old_version', 0) != 0:
      raise ValueError('`old_version must be 0 for a new Operation')

  if 'uss_base_url' not in json:
    raise ValueError('Missing `uss_base_url` in Operation request')

  if extents.time_start is None:
    raise ValueError('Missing `time_start` in Operation request')
  if extents.time_end is None:
    raise ValueError('Missing `time_end` in Operation request')
  if extents.altitude_lo is None:
    raise ValueError('Missing `altitude_lower` in Operation extents')
  if extents.altitude_hi is None:
    raise ValueError('Missing `altitude_upper` in Operation extents')

  version = json.get('old_version', 0) + 1
  ovn = make_ovn()

  return Operation(
    id=id_uuid,
    owner=owner,
    version=version,
    ovn=ovn,
    vol4=extents,
    uss_base_url=json['uss_base_url'],
    subscription=subscription_id)
