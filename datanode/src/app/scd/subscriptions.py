from datetime import datetime, timezone
import logging
import re
from typing import Dict, List, Iterable, Optional, Set, Tuple
import uuid

from app.dsslib import format_utils
from app.scd import geo


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('Subscriptions')

UUID_VALIDATOR = re.compile('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[8-b][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$')


class Subscription(object):
  """Data structure for an SCD Subscription."""
  id: uuid.UUID
  owner: str
  version: int
  notification_index: int
  vol4: geo.Volume4
  uss_base_url: str
  notify_for_operations: bool
  notify_for_constraints: bool
  implicit_subscription: bool
  dependent_operations: Set[uuid.UUID]

  def __init__(
      self,
      id: uuid.UUID,
      owner: str,
      version: int,
      notification_index: int,
      vol4: geo.Volume4,
      uss_base_url: str,
      notify_for_operations: bool,
      notify_for_constraints: bool,
      implicit_subscription: bool,
      dependent_operations: Set[uuid.UUID]):
    """Create new SCD Subscription."""
    self.id = id
    self.owner = owner
    self.version = version
    self.notification_index = notification_index
    self.vol4 = vol4
    self.uss_base_url = uss_base_url
    self.notify_for_operations = notify_for_operations
    self.notify_for_constraints = notify_for_constraints
    self.implicit_subscription = implicit_subscription
    self.dependent_operations = dependent_operations

  def to_dict(self):
    return {
      'id': str(self.id),
      'version': self.version,
      'notification_index': self.notification_index,
      'time_start': format_utils.format_ts(self.vol4.time_start),
      'time_end': format_utils.format_ts(self.vol4.time_end),
      'uss_base_url': self.uss_base_url,
      'notify_for_operations': self.notify_for_operations,
      'notify_for_constraints': self.notify_for_constraints,
      'implicit_subscription': self.implicit_subscription,
      'dependent_operations': [str(id) for id in self.dependent_operations]
    }


def from_request(id: str, json: Dict, owner: str, existing_subscription: Optional[Subscription], geo_config: geo.Config) -> Subscription:
  """Create an SCD Subscription from a request structure."""

  id_uuid = uuid.UUID(id)

  if existing_subscription is not None:
    if 'old_version' not in json:
      raise ValueError('Missing `old_version` to update existing Subscription')
    elif json['old_version'] != existing_subscription.version:
      raise ValueError('`old_version` does not match existing Subscription version')
  else:
    if json.get('old_version', 0) != 0:
      raise ValueError('`old_version must be 0 for a new Subscription')

  if 'uss_base_url' not in json:
    raise ValueError('Missing `uss_base_url` in Subscription request')

  if 'extents' not in json:
    raise ValueError('Missing `extents` in Subscription request')
  vol4 = geo.expand_volume4(json['extents'], geo_config.min_s2_level, geo_config.max_s2_level)
  if vol4.time_start is None:
    vol4.time_start = datetime.now(timezone.utc)

  version = json.get('old_version', 0) + 1

  return Subscription(
      id=id_uuid,
      owner=owner,
      version=version,
      notification_index=0 if existing_subscription is None else existing_subscription.notification_index,
      vol4=vol4,
      uss_base_url=json['uss_base_url'],
      notify_for_operations=json.get('notify_for_operations', False),
      notify_for_constraints=json.get('notify_for_constraints', False),
      implicit_subscription=False,
      dependent_operations=set() if existing_subscription is None else existing_subscription.dependent_operations)


def get_subscribers(subs: Iterable[Subscription]) -> List[Dict]:
  subscribers_by_url: Dict[str, List[Tuple[uuid.UUID, int]]] = {}
  for sub in subs:
    if sub.uss_base_url not in subscribers_by_url:
      subscribers_by_url[sub.uss_base_url] = []
    subscribers_by_url[sub.uss_base_url].append((sub.id, sub.notification_index))
  subscribers = []
  for url in subscribers_by_url:
    subscriptions = []
    for subscription_id, notification_index in subscribers_by_url[url]:
      subscriptions.append({'subscription_id': subscription_id, 'notification_index': notification_index})
    subscribers.append({'uss_base_url': url, 'subscriptions': subscriptions})
  return subscribers
