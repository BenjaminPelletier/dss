import logging
import uuid

import flask

import app
from app import webapp
from app.auth import authorization
from app.scd import scopes, errors, geo, subscriptions


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('SCDSubscriptions')


@webapp.route('/dss/v1/subscriptions/query', methods=['POST'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION, scopes.CONSTRAINT_CONSUMPTION])
def QuerySubscriptions():
  req = flask.request.json
  area_of_interest = req.get('area_of_interest', None)
  if not area_of_interest:
    raise ValueError('Missing area_of_interest in query request')
  geo_config = webapp.config['SCD_GEO_CONFIG']
  vol4 = geo.expand_volume4(area_of_interest, geo_config.min_s2_level, geo_config.max_s2_level)
  subscriptions = app.scd_storage.find_subscriptions(vol4, flask.request.jwt.client_id)

  return flask.jsonify({
    'subscriptions': [subscription.to_dict() for subscription in subscriptions]
  })


@webapp.route('/dss/v1/subscriptions/<id>', methods=['GET'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION, scopes.CONSTRAINT_CONSUMPTION])
def GetSubscription(id):
  subscription_id = uuid.UUID(id)
  subscription = app.scd_storage.get_subscription(subscription_id)
  if subscription is not None:
    return flask.jsonify({'subscription': subscription.to_dict()})
  else:
    raise errors.NotFoundError('Subscription not found')


@webapp.route('/dss/v1/subscriptions/<id>', methods=['PUT'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION, scopes.CONSTRAINT_CONSUMPTION])
def PutSubscription(id):
  subscription_id = uuid.UUID(id)
  existing_subscription = app.scd_storage.get_subscription(subscription_id)
  if existing_subscription is not None and existing_subscription.owner != flask.request.jwt.client_id:
    raise errors.NotOwnedError('Only the owner may modify a subscription')
  new_subscription = subscriptions.from_request(
    id, flask.request.json, flask.request.jwt.client_id, existing_subscription, webapp.config['SCD_GEO_CONFIG'])
  new_subscription.version += 1
  app.scd_storage.upsert_subscription(new_subscription)

  #TODO: find Operations and Constraints

  return flask.jsonify({
    'subscription': new_subscription.to_dict(),
    'operations': [],
    'constraints': []
  }), 200 if existing_subscription is not None else 201

@webapp.route('/dss/v1/subscriptions/<id>', methods=['DELETE'])
@authorization.requires_scope([scopes.STRATEGIC_COORDINATION, scopes.CONSTRAINT_CONSUMPTION])
def DeleteSubscription(id):
  subscription_id = uuid.UUID(id)
  old_subscription = app.scd_storage.get_subscription(subscription_id)
  if old_subscription is None:
    raise errors.NotFoundError('Subscription not found')
  if old_subscription.owner != flask.request.jwt.client_id:
    raise errors.NotOwnedError('Only the owner may delete an subscription')
  app.scd_storage.delete_subscription(subscription_id)

  return flask.jsonify({'subscription_reference': old_subscription.to_dict()})
