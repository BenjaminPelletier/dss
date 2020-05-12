import copy
from datetime import datetime, timedelta
import threading
from typing import Dict
import unittest
import uuid

import requests

from app import dss, webapp
from app.scd import test_utils
import app.auth.config


_UNIX_EPOCH = datetime.utcfromtimestamp(0)
SCD_URL = 'http://localhost:5001'


class SCDSubscriptionsTestCase(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    test_utils.test_lock.acquire()
    cls.token_keypair = test_utils.make_key_pair()
    webapp.config['TOKEN_PUBLIC_KEY'] = app.auth.config.fix_key(cls.token_keypair.public_key).encode('utf-8')
    webapp.config['TOKEN_AUDIENCE'] = 'example.com'
    def run_webapp():
      webapp.run(host='0.0.0.0', port=5001)
    cls.webapp_thread = threading.Thread(target=run_webapp, daemon=True)
    cls.webapp_thread.start()

  @classmethod
  def tearDownClass(cls):
    test_utils.test_lock.release()

  def _make_headers(self, sub, scope):
    token = test_utils.make_token(self.token_keypair.private_key, sub, scope, 'example.com', 'example.com')
    return {'Authorization': 'Bearer ' + token}

  def _nominal_subscription_cycle(
      self, original_subscription: Dict, original_query: Dict, mutated_subscription: Dict, mutated_query: Dict):
    id = str(uuid.uuid4())
    headers = self._make_headers('testuss', 'utm.strategic_coordination')

    # Make sure the Subscription doesn't exist already (by ID)
    resp = requests.get(SCD_URL + '/dss/v1/subscriptions/' + id, headers=headers)
    self.assertEqual(resp.status_code, 404, resp.content)

    # Make sure the Subscription doesn't exist already (by query)
    resp = requests.post(SCD_URL + '/dss/v1/subscriptions/query', headers=headers, json={
      'area_of_interest': original_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    self.assertEqual(len(resp.json()['subscriptions']), 0)

    # Create the Subscription
    resp = requests.put(SCD_URL + '/dss/v1/subscriptions/' + id, headers=headers, json=original_subscription)
    self.assertEqual(resp.status_code, 201, resp.content)
    sub_created = resp.json()

    # Read the Subscription
    resp = requests.get(SCD_URL + '/dss/v1/subscriptions/' + id, headers=headers)
    self.assertEqual(resp.status_code, 200, resp.content)
    sub_get = resp.json()
    self.assertEqual(sub_created['subscription'], sub_get['subscription'])

    # Query the Subscription
    resp = requests.post(SCD_URL + '/dss/v1/subscriptions/query', headers=headers, json={
      'area_of_interest': original_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    subs_queried = resp.json()['subscriptions']
    self.assertEqual(len(subs_queried), 1)
    self.assertEqual(subs_queried[0], sub_get['subscription'])

    # Mutate the Subscription
    mutated_subscription['old_version'] = sub_created['subscription']['version']
    resp = requests.put(SCD_URL + '/dss/v1/subscriptions/' + id, headers=headers, json=mutated_subscription)
    self.assertEqual(resp.status_code, 200, resp.content)
    sub_mutated = resp.json()

    # Read the mutated Subscription
    resp = requests.get(SCD_URL + '/dss/v1/subscriptions/' + id, headers=headers)
    self.assertEqual(resp.status_code, 200, resp.content)
    sub_get = resp.json()
    self.assertEqual(sub_mutated['subscription'], sub_get['subscription'])

    # Query the mutated Subscription
    resp = requests.post(SCD_URL + '/dss/v1/subscriptions/query', headers=headers, json={
      'area_of_interest': mutated_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    subs_queried = resp.json()['subscriptions']
    self.assertEqual(len(subs_queried), 1)
    self.assertEqual(subs_queried[0], sub_get['subscription'])

    # Delete the Subscription
    resp = requests.delete(SCD_URL + '/dss/v1/subscriptions/' + id, headers=headers)
    self.assertEqual(resp.status_code, 200, resp.content)

    # Make sure the Subscription can't be found by ID any more
    resp = requests.get(SCD_URL + '/dss/v1/subscriptions/' + id, headers=headers)
    self.assertEqual(resp.status_code, 404, resp.content)

    # Make sure the Subscription can't be found by query any more
    resp = requests.post(SCD_URL + '/dss/v1/subscriptions/query', headers=headers, json={
      'area_of_interest': mutated_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    self.assertEqual(len(resp.json()['subscriptions']), 0)

  def testStatus(self):
    resp = requests.get(SCD_URL + '/status')
    self.assertEqual(resp.status_code, 200, resp.content)

  def testSubscriptions_Nominal(self):
    self.maxDiff = 2000

    original_subscription = {
      "extents": test_utils.make_vol4(
        None, datetime.utcnow() + timedelta(seconds=90),
        0, 3000,
        circle=test_utils.make_circle(12, -34, 300)),
      "uss_base_url": "https://utm_uss.com/utm",
      "notify_for_operations": False,
      "notify_for_constraints": False
    }

    original_query = test_utils.make_vol4(
      datetime.utcnow(), datetime.utcnow() + timedelta(seconds=5),
      0, 1000,
      polygon=test_utils.make_polygon([
        (11.999, -34.001),
        (11.999, -33.999),
        (12.001, -33.999),
        (12.001, -34.001)
      ]))

    mutated_subscription = copy.deepcopy(original_subscription)
    del mutated_subscription['extents']['volume']['outline_circle']
    mutated_subscription['extents']['volume']['outline_polygon'] = test_utils.make_polygon([
      (69.999, 169.999),
      (70.001, 169.999),
      (70.001, 170.001),
      (69.999, 170.001)
    ])
    mutated_subscription['extents']['volume']['altitude_upper']['value'] = 1000

    mutated_query = test_utils.make_vol4(
      datetime.utcnow(), datetime.utcnow() + timedelta(seconds=10),
      0, 1000,
      circle=test_utils.make_circle(70.002, 170, 400))

    self._nominal_subscription_cycle(
      original_subscription,
      original_query,
      mutated_subscription,
      mutated_query
    )


if __name__ == '__main__':
  unittest.main()
