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
SCD_URL = 'http://localhost:5002'


class SCDOperationsTestCase(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    test_utils.test_lock.acquire()
    cls.token_keypair = test_utils.make_key_pair()
    webapp.config['TOKEN_PUBLIC_KEY'] = app.auth.config.fix_key(cls.token_keypair.public_key).encode('utf-8')
    webapp.config['TOKEN_AUDIENCE'] = 'example.com'
    def run_webapp():
      webapp.run(host='0.0.0.0', port=5002)
    cls.webapp_thread = threading.Thread(target=run_webapp, daemon=True)
    cls.webapp_thread.start()

  @classmethod
  def tearDownClass(cls):
    test_utils.test_lock.release()

  def _make_headers(self, sub, scope):
    token = test_utils.make_token(self.token_keypair.private_key, sub, scope, 'example.com', 'example.com')
    return {'Authorization': 'Bearer ' + token}

  def _isolated_operation_cycle(
      self, original_operation: Dict, original_query: Dict, mutated_operation: Dict, mutated_query: Dict):
    id = str(uuid.uuid4())
    headers = self._make_headers('uss1', 'utm.strategic_coordination')

    # Make sure the Operation doesn't exist already (by ID)
    resp = requests.get(SCD_URL + '/dss/v1/operations/' + id, headers=headers)
    self.assertEqual(resp.status_code, 404, resp.content)

    # Make sure the Operation doesn't exist already (by query)
    resp = requests.post(SCD_URL + '/dss/v1/operations/query', headers=headers, json={
      'area_of_interest': original_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    self.assertEqual(len(resp.json()['operation_references']), 0)

    # Create the Operation
    resp = requests.put(SCD_URL + '/dss/v1/operations/' + id, headers=headers, json=original_operation)
    self.assertEqual(resp.status_code, 201, resp.content)
    op_created = resp.json()

    # Read the Operation
    resp = requests.get(SCD_URL + '/dss/v1/operations/' + id, headers=headers)
    self.assertEqual(resp.status_code, 200, resp.content)
    op_get = resp.json()
    self.assertEqual(op_created['operation_reference'], op_get['operation_reference'])

    # Query the Operation
    resp = requests.post(SCD_URL + '/dss/v1/operations/query', headers=headers, json={
      'area_of_interest': original_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    ops_queried = resp.json()['operation_references']
    self.assertEqual(len(ops_queried), 1)
    self.assertEqual(ops_queried[0], op_get['operation_reference'])

    # Mutate the Operation
    mutated_operation['old_version'] = op_created['operation_reference']['version']
    if 'key' not in mutated_operation:
      mutated_operation['key'] = []
    mutated_operation['key'].append(op_created['operation_reference']['ovn'])
    mutated_operation['subscription_id'] = op_created['operation_reference']['subscription_id']
    resp = requests.put(SCD_URL + '/dss/v1/operations/' + id, headers=headers, json=mutated_operation)
    self.assertEqual(resp.status_code, 200, resp.content)
    op_mutated = resp.json()

    # Read the mutated Operation
    resp = requests.get(SCD_URL + '/dss/v1/operations/' + id, headers=headers)
    self.assertEqual(resp.status_code, 200, resp.content)
    op_get = resp.json()
    self.assertEqual(op_mutated['operation_reference'], op_get['operation_reference'])

    # Query the mutated Operation
    resp = requests.post(SCD_URL + '/dss/v1/operations/query', headers=headers, json={
      'area_of_interest': mutated_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    ops_queried = resp.json()['operation_references']
    self.assertEqual(len(ops_queried), 1)
    self.assertEqual(ops_queried[0], op_get['operation_reference'])

    # Delete the Operation
    resp = requests.delete(SCD_URL + '/dss/v1/operations/' + id, headers=headers)
    self.assertEqual(resp.status_code, 200, resp.content)

    # Make sure the Operation can't be found by ID any more
    resp = requests.get(SCD_URL + '/dss/v1/operations/' + id, headers=headers)
    self.assertEqual(resp.status_code, 404, resp.content)

    # Make sure the Operation can't be found by query any more
    resp = requests.post(SCD_URL + '/dss/v1/operations/query', headers=headers, json={
      'area_of_interest': mutated_query
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    self.assertEqual(len(resp.json()['operation_references']), 0)

  def testStatus(self):
    resp = requests.get(SCD_URL + '/status')
    self.assertEqual(resp.status_code, 200, resp.content)

  def testOperations_Nominal(self):
    self.maxDiff = 2000

    original_operation = {
      "extents": [test_utils.make_vol4(
        datetime.utcnow(), datetime.utcnow() + timedelta(seconds=90),
        0, 3000,
        circle=test_utils.make_circle(-45, 145, 300))],
      "state": "Accepted",
      "uss_base_url": "https://utm_uss.com/utm",
      "new_subscription": {
        "uss_base_url": "https://utm_uss.com/utm",
        "notify_for_constraints": False
      }
    }

    original_query = test_utils.make_vol4(
      datetime.utcnow(), datetime.utcnow() + timedelta(seconds=5),
      0, 1000,
      polygon=test_utils.make_polygon([
        (-44.999, 145.001),
        (-44.999, 144.999),
        (-45.001, 144.999),
        (-45.001, 145.001)
      ]))

    mutated_operation = copy.deepcopy(original_operation)
    del mutated_operation['new_subscription']
    mutated_operation['state'] = 'Activated'
    mutated_operation['extents'][0]['volume']['altitude_upper']['value'] = 1000

    mutated_query = copy.deepcopy(original_query)
    mutated_query['time_end'] = test_utils.make_time(datetime.utcnow() + timedelta(seconds=10))

    self._isolated_operation_cycle(
      original_operation,
      original_query,
      mutated_operation,
      mutated_query
    )

  def testTwoOperations_Simple(self):
    op1_id = str(uuid.uuid4())
    sub2_id = str(uuid.uuid4())
    op2_id = str(uuid.uuid4())
    headers1 = self._make_headers('uss1', 'utm.strategic_coordination')
    headers2 = self._make_headers('uss2', 'utm.strategic_coordination')

    op1 = {
      "extents": [test_utils.make_vol4(
        datetime.utcnow(), datetime.utcnow() + timedelta(seconds=90),
        0, 3000,
        circle=test_utils.make_circle(85, 0, 100))],
      "state": "Accepted",
      "uss_base_url": "https://uss1.com/utm",
      "new_subscription": {
        "uss_base_url": "https://uss1.com/utm",
        "notify_for_constraints": False
      }
    }

    sub2 = {
      "extents": test_utils.make_vol4(
        datetime.utcnow() - timedelta(seconds=1), datetime.utcnow() + timedelta(seconds=180),
        0, 3000,
        circle=test_utils.make_circle(85, 0, 300)),
      "uss_base_url": "https://uss2.com/utm",
      "notify_for_operations": True,
      "notify_for_constraints": False
    }

    op2 = {
      "extents": [test_utils.make_vol4(
        datetime.utcnow(), datetime.utcnow() + timedelta(seconds=90),
        0, 1000,
        circle=test_utils.make_circle(85, 0, 150))],
      "state": "Accepted",
      "uss_base_url": "https://uss2.com/utm",
    }

    # Create op1
    resp = requests.put(SCD_URL + '/dss/v1/operations/' + op1_id, headers=headers1, json=op1)
    self.assertEqual(resp.status_code, 201, resp.content)
    op1_created = resp.json()

    # Establish area-based sub2
    resp = requests.put(SCD_URL + '/dss/v1/subscriptions/' + sub2_id, headers=headers2, json=sub2)
    self.assertEqual(resp.status_code, 201, resp.content)
    sub2_created = resp.json()
    self.assertEqual(len(sub2_created['operations']), 1)
    self.assertEqual(sub2_created['operations'][0]['id'], op1_created['operation_reference']['id'])

    # Create op2
    op2['subscription_id'] = sub2_created['subscription']['id']
    op2['key'] = [op1_created['operation_reference']['ovn']]
    resp = requests.put(SCD_URL + '/dss/v1/operations/' + op2_id, headers=headers2, json=op2)
    self.assertEqual(resp.status_code, 201, resp.content)
    op2_created = resp.json()
    subscribers = op2_created['subscribers']
    self.assertEqual(len(subscribers), 2)
    self.assertIn('https://uss1.com/utm', [sub['uss_base_url'] for sub in subscribers])
    self.assertIn('https://uss2.com/utm', [sub['uss_base_url'] for sub in subscribers])

    # Delete op1
    resp = requests.delete(SCD_URL + '/dss/v1/operations/' + op1_id, headers=headers1)
    self.assertEqual(resp.status_code, 200, resp.content)
    op1_deleted = resp.json()
    self.assertEqual(len(op1_deleted['subscribers']), 1)
    self.assertEqual(op1_deleted['subscribers'][0]['uss_base_url'], 'https://uss2.com/utm')

    # Delete op2
    resp = requests.delete(SCD_URL + '/dss/v1/operations/' + op2_id, headers=headers2)
    self.assertEqual(resp.status_code, 200, resp.content)
    op1_deleted = resp.json()
    self.assertEqual(len(op1_deleted['subscribers']), 1)
    self.assertEqual(op1_deleted['subscribers'][0]['uss_base_url'], 'https://uss2.com/utm')


if __name__ == '__main__':
  unittest.main()
