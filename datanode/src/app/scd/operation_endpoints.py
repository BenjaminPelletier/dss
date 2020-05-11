import logging
from typing import Dict, List, Tuple
import uuid

import flask

import app
from app import webapp
from app.auth import authorization
from app.scd import scopes, errors, geo, operations, subscriptions


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('SCDOperations')


@webapp.route('/dss/v1/operations/query', methods=['POST'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION])
def QueryOperations():
  req = flask.request.json
  area_of_interest = req.get('area_of_interest', None)
  if not area_of_interest:
    raise ValueError('Missing area_of_interest in query request')
  geo_config = webapp.config['SCD_GEO_CONFIG']
  vol4 = geo.expand_volume4(area_of_interest, geo_config.min_s2_level, geo_config.max_s2_level)
  operations = app.scd_storage.find_operations(vol4)

  caller = flask.request.jwt.client_id
  return flask.jsonify({
    'operation_references': [operation.to_dict(include_ovn=operation.owner == caller) for operation in operations]
  })


@webapp.route('/dss/v1/operations/<id>', methods=['GET'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION])
def GetOperation(id):
  operation_id = uuid.UUID(id)
  operation = app.scd_storage.get_operation(operation_id)
  if operation is not None:
    include_ovn = flask.request.jwt.client_id == operation.owner
    return flask.jsonify({'operation_reference': operation.to_dict(include_ovn=include_ovn)})
  else:
    raise errors.NotFoundError('Operation not found')


@webapp.route('/dss/v1/operations/<id>', methods=['PUT'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION])
def PutOperation(id):
  operation_id = uuid.UUID(id)
  json = flask.request.json
  owner = flask.request.jwt.client_id

  geo_config = webapp.config['SCD_GEO_CONFIG']
  vol4s_json = json.get('extents', None)
  if not vol4s_json:
    raise ValueError('Missing `extents`')
  if not isinstance(vol4s_json, list):
    raise ValueError('Expected `extents` to be a list of Volume4D')
  vol4s = [geo.expand_volume4(vol4_json, geo_config.min_s2_level, geo_config.max_s2_level)
           for vol4_json in vol4s_json]
  vol4 = geo.combine_volume4s(vol4s)

  existing_operation = app.scd_storage.get_operation(operation_id)
  if existing_operation is not None and existing_operation.owner != owner:
    raise errors.NotOwnedError('Only the owner may modify an operation reference')

  if 'subscription_id' in json:
    sub = app.scd_storage.get_subscription(uuid.UUID(json['subscription_id']))
    if sub is None:
      raise ValueError('Specified Subscription does not exist')
    sub.dependent_operations.add(operation_id)
    sub.version += 1
    if not sub.vol4.contains(vol4):
      raise ValueError('Specified Subscription does not cover the entire Operation Volume4D')
  elif 'new_subscription' in json:
    uss_base_url = json['new_subscription'].get('uss_base_url', None)
    if not uss_base_url:
      raise ValueError('Missing `uss_base_url` from `new_subscription`')
    notify_for_constraints = json['new_subscription'].get('notify_for_constraints')
    sub = subscriptions.Subscription(
      uuid.uuid4(), owner, 1, 0, vol4, uss_base_url, True, notify_for_constraints, True, {operation_id})
  else:
    raise ValueError('One of `subscription_id` or `new_subscription` must be specified')

  new_operation = operations.from_request(id, json, owner, sub.id, existing_operation, vol4)
  new_operation.version += 1

  app.scd_storage.upsert_operation(new_operation)
  app.scd_storage.upsert_subscription(sub)

  subscribers_json = subscriptions.get_subscribers(app.scd_storage.find_subscriptions(vol4))

  return flask.jsonify({
    'operation_reference': new_operation.to_dict(include_ovn=True),
    'subscribers': subscribers_json
  }), 200 if existing_operation is not None else 201

@webapp.route('/dss/v1/operations/<id>', methods=['DELETE'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION])
def DeleteOperation(id):
  operation_id = uuid.UUID(id)
  old_operation = app.scd_storage.get_operation(operation_id)
  if old_operation is None:
    raise errors.NotFoundError('Operation not found')
  if old_operation.owner != flask.request.jwt.client_id:
    raise errors.NotOwnedError('Only the owner may delete an operation reference')
  app.scd_storage.delete_operation(operation_id)

  sub = app.scd_storage.get_subscription(old_operation.subscription)
  sub.dependent_operations.remove(operation_id)
  if sub.implicit_subscription and not sub.dependent_operations:
    app.scd_storage.delete_subscription(sub.id)
  else:
    sub.version += 1
    app.scd_storage.upsert_subscription(sub)

  subscribers_json = subscriptions.get_subscribers(app.scd_storage.find_subscriptions(old_operation.vol4))

  return flask.jsonify({
    'operation_reference': old_operation.to_dict(include_ovn=True),
    'subscribers': subscribers_json
  })
