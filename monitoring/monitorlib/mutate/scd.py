import datetime
from typing import Dict, List, Optional

import s2sphere
import yaml
from yaml.representer import Representer

from monitoring.monitorlib import infrastructure, scd
from monitoring.monitorlib import fetch


class MutatedSubscription(fetch.Query):
  @property
  def success(self) -> bool:
    return not self.errors

  @property
  def errors(self) -> List[str]:
    if self.status_code != 200:
      return ['Failed to {} SCD Subscription ({})'.format(self.mutation, self.status_code)]
    if self.json_result is None:
      return ['Response did not contain valid JSON']
    sub = self.subscription
    if sub is None or not sub.valid:
      return ['Response returned an invalid Subscription']

  @property
  def subscription(self) -> Optional[scd.Subscription]:
    if self.json_result is None:
      return None
    sub = self.json_result.get('subscription', None)
    if not sub:
      return None
    return scd.Subscription(sub)

  @property
  def mutation(self) -> str:
    return self['mutation']
yaml.add_representer(MutatedSubscription, Representer.represent_dict)


def put_subscription(utm_client: infrastructure.DSSTestSession,
                     area: s2sphere.LatLngRect,
                     start_time: datetime.datetime,
                     end_time: datetime.datetime,
                     base_url: str,
                     subscription_id: str,
                     min_alt_m: float=0,
                     max_alt_m: float=3048,
                     old_version: int=0) -> MutatedSubscription:
  body = {
    'extents': scd.make_vol4(
      start_time, end_time, min_alt_m, max_alt_m,
      polygon=scd.make_polygon(latlngrect=area)),
    'old_version': old_version,
    'uss_base_url': base_url,
    'notify_for_operations': True,
    'notify_for_constraints': True,
  }
  url = '/dss/v1/subscriptions/{}'.format(subscription_id)
  result = MutatedSubscription(fetch.query_and_describe(
    utm_client, 'PUT', url, json=body, scope=scd.SCOPE_SC))
  result['mutation'] = 'create' if old_version == 0 else 'update'
  return result


def delete_subscription(utm_client: infrastructure.DSSTestSession,
                        subscription_id: str) -> MutatedSubscription:
  url = '/dss/v1/subscriptions/{}'.format(subscription_id)
  result = MutatedSubscription(fetch.query_and_describe(
    utm_client, 'DELETE', url, scope=scd.SCOPE_SC))
  result['mutation'] = 'delete'
  return result


class SubscriberToNotify(dict):
  @property
  def base_url(self) -> str:
    return self['uss_base_url']

  @property
  def subscriptions(self) -> List[Dict]:
    return self['subscriptions']
yaml.add_representer(SubscriberToNotify, Representer.represent_dict)


class MutatedEntityReference(fetch.Query):
  @property
  def success(self) -> bool:
    return not self.errors

  @property
  def entity_type(self) -> str:
    return self['entity_type']

  @property
  def mutation(self) -> str:
    return self['mutation']

  @property
  def errors(self) -> List[str]:
    if self.status_code != 200 and self.status_code != 201:
      return ['Failed to {} SCD {} ({})'.format(self.mutation, self.entity_type, self.status_code)]
    if self.json_result is None:
      return ['Response did not contain valid JSON']
    ref = self.reference
    if ref is None or not ref.valid:
      return ['Response returned an invalid {}'.format(self.entity_type)]

  @property
  def reference(self) -> Optional[scd.EntityReference]:
    if self.json_result is None:
      return None
    entity_ref = self.json_result.get(self.entity_type)
    if not entity_ref:
      return None
    return scd.EntityReference(entity_ref)

  @property
  def subscribers(self) -> List[SubscriberToNotify]:
    return [SubscriberToNotify(subscriber)
            for subscriber in self.json_result.get('subscribers', [])]
yaml.add_representer(MutatedEntityReference, Representer.represent_dict)


class MutatedEntity(dict):
  @classmethod
  def from_result(cls,
                  entity_type: str,
                  ref_result: MutatedEntityReference,
                  notifications: Dict[str, fetch.Query]):
    result = MutatedEntity()
    result['entity_type'] = entity_type
    result['ref_result'] = ref_result
    result['notifications'] = notifications
    return result

  @property
  def entity_type(self) -> str:
    return self['entity_type']

  @property
  def ref_result(self) -> MutatedEntityReference:
    return fetch.coerce(self['ref_result'], MutatedEntityReference)

  @property
  def notifications(self) -> Dict[str, fetch.Query]:
    return {k: fetch.coerce(v, fetch.Query) for k, v in self['notifications'].items()}
yaml.add_representer(MutatedEntity, Representer.represent_dict)


def put_constraint(utm_client: infrastructure.DSSTestSession,
                   details: Dict,
                   base_url: str,
                   constraint_id: str,
                   old_version: int=0) -> MutatedEntity:
  # PUT Constraint reference in the DSS
  body = {
    'extents': details['volumes'],
    'old_version': old_version,
    'uss_base_url': base_url,
  }
  url = '/dss/v1/constraint_references/{}'.format(constraint_id)
  ref_result = MutatedEntityReference(fetch.query_and_describe(
    utm_client, 'PUT', url, json=body, scope=scd.SCOPE_CM))
  ref_result['mutation'] = 'create' if old_version == 0 else 'update'
  ref_result['entity_type'] = 'constraint_reference'

  # Notify subscribers
  entity = {
    'reference': ref_result.reference,
    'details': details,
  }
  notifications: Dict[str, fetch.Query] = {}
  for subscriber in ref_result.subscribers:
    body = {
      'constraint': entity,
      'constraint_id': constraint_id,
      'subscriptions': subscriber.subscriptions,
    }
    url = '{}/uss/v1/constraints'.format(subscriber.base_url)
    notifications[subscriber.base_url] = fetch.query_and_describe(
      utm_client, 'POST', url, json=body, scope=scd.SCOPE_CM)

  return MutatedEntity.from_result('constraint', ref_result, notifications)


def _delete_entity(utm_client: infrastructure.DSSTestSession,
                   entity_type: str,
                   scope: str,
                   entity_id: str) -> MutatedEntity:
  # DELETE Entity reference in the DSS
  url = '/dss/v1/{}_references/{}'.format(entity_type, entity_id)
  ref_result = MutatedEntityReference(fetch.query_and_describe(
    utm_client, 'DELETE', url, scope=scope))
  ref_result['mutation'] = 'delete'
  ref_result['entity_type'] = entity_type

  # Notify subscribers
  notifications: Dict[str, fetch.Query] = {}
  for subscriber in ref_result.subscribers:
    body = {
      '{}_id'.format(entity_type): entity_id,
      'subscriptions': subscriber.subscriptions,
    }
    url = '{}/uss/v1/{}s'.format(subscriber.base_url, entity_type)
    notifications[subscriber.base_url] = fetch.query_and_describe(
      utm_client, 'POST', url, json=body, scope=scope)

  return MutatedEntity.from_result(entity_type, ref_result, notifications)


def delete_constraint(utm_client: infrastructure.DSSTestSession,
                      constraint_id: str) -> MutatedEntity:
  return _delete_entity(utm_client, 'constraint', scd.SCOPE_CM, constraint_id)
