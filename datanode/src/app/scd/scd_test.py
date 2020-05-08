import collections
import copy
from datetime import datetime, timedelta
import os
import threading
from typing import Dict, List, Optional, Tuple
import unittest
import uuid

from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
import jwt
import requests

# Note: Do not import any app modules here; doing so will initialize the webapp configuration with the current
# os.environ which doesn't yet contain TOKEN_PUBLIC_KEY.

_UNIX_EPOCH = datetime.utcfromtimestamp(0)
SCD_URL = 'http://localhost:5000'


KeyPair = collections.namedtuple('KeyPair', 'private_key public_key')


def make_key_pair() -> KeyPair:
  """Create a public/private RSA key pair.
  Returns:
    Public and private keys in KeyPair using PEM text format.
  """
  key = rsa.generate_private_key(
    backend=crypto_default_backend(),
    public_exponent=65537,
    key_size=2048
  )
  private_key = key.private_bytes(
    crypto_serialization.Encoding.PEM,
    crypto_serialization.PrivateFormat.PKCS8,
    crypto_serialization.NoEncryption()
  ).decode('utf-8')
  public_key = key.public_key().public_bytes(
    encoding=crypto_serialization.Encoding.PEM,
    format=crypto_serialization.PublicFormat.SubjectPublicKeyInfo
  ).decode('utf-8')
  return KeyPair(private_key, public_key)


def make_token(private_key: str, sub: str, scopes: str, issuer: str) -> str:
  timestamp = int((datetime.utcnow() - _UNIX_EPOCH).total_seconds())
  payload = {
    'sub': sub,
    'nbf': timestamp - 1,
    'scope': scopes,
    'iss': issuer,
    'exp': timestamp + 3600,
    'jti': str(uuid.uuid4()),
  }

  return jwt.encode(payload, key=private_key, algorithm='RS256').decode('utf-8')


def make_vol4(
    t0: Optional[datetime] = None,
    t1: Optional[datetime] = None,
    alt0: Optional[float] = None,
    alt1: Optional[float] = None,
    circle: Dict = None,
    polygon: Dict = None) -> Dict:
  vol3 = dict()
  if circle is not None:
    vol3['outline_circle'] = circle
  if polygon is not None:
    vol3['outline_polygon'] = polygon
  if alt0 is not None:
    vol3['altitude_lower'] = {
      'value': alt0,
      'reference': 'W84',
      'units': 'M'
    }
  if alt1 is not None:
    vol3['altitude_upper'] = {
      'value': alt1,
      'reference': 'W84',
      'units': 'M'
    }
  vol4 = {'volume': vol3}
  if t0 is not None:
    vol4['time_start'] = {
      'value': t0.isoformat(),
      'format': 'RFC3339'
    }
  if t1 is not None:
    vol4['time_end'] = {
      'value': t1.isoformat(),
      'format': 'RFC3339'
    }
  return vol4


def make_circle(lat: float, lng: float, radius: float) -> Dict:
  return {
    "type": "Feature",
    "geometry": {
      "type": "Point",
      "coordinates": [lng, lat]
    },
    "properties": {
      "radius": {
        "value": radius,
        "units": "M"
      }
    }
  }


def make_polygon(coords: List[Tuple[float, float]]) -> Dict:
  full_coords = coords.copy()
  full_coords.append(coords[0])
  return {
    "type": "Polygon",
    "coordinates": [ [[lng, lat] for (lat, lng) in full_coords] ]
  }

test_lock = threading.Lock()


class SCDTestCase(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    test_lock.acquire()
    cls.token_keypair = make_key_pair()
    os.environ['TOKEN_PUBLIC_KEY'] = cls.token_keypair.public_key
    # Import dss and webapp here because TOKEN_PUBLIC_KEY is now available
    from app import dss, webapp
    def run_webapp():
      webapp.run(host='0.0.0.0', port=5000)
    cls.webapp_thread = threading.Thread(target=run_webapp, daemon=True)
    cls.webapp_thread.start()

  @classmethod
  def tearDownClass(cls):
    test_lock.release()

  def _make_headers(self, sub, scope):
    token = make_token(self.token_keypair.private_key, sub, scope, 'example.com')
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
      'area_of_interest': make_vol4(datetime.utcnow(), datetime.utcnow(), 0, 1000, make_circle(20.0001, 100.0001, 200))
    })
    self.assertEqual(resp.status_code, 200, resp.content)
    self.assertEqual(len(resp.json()['subscriptions']), 0)

  def testStatus(self):
    resp = requests.get(SCD_URL + '/status')
    self.assertEqual(resp.status_code, 200, resp.content)

  def testSubscriptions_Nominal(self):
    self.maxDiff = 2000

    original_subscription = {
      "extents": make_vol4(
        None, datetime.utcnow() + timedelta(seconds=90),
        0, 3000,
        circle=make_circle(12, -34, 300)),
      "uss_base_url": "https://utm_uss.com/utm",
      "notify_for_operations": False,
      "notify_for_constraints": False
    }

    original_query = make_vol4(
      datetime.utcnow(), datetime.utcnow() + timedelta(seconds=5),
      0, 1000,
      polygon=make_polygon([
        (11.999, -34.001),
        (11.999, -33.999),
        (12.001, -33.999),
        (12.001, -34.001)
      ]))

    mutated_subscription = copy.deepcopy(original_subscription)
    del mutated_subscription['extents']['volume']['outline_circle']
    mutated_subscription['extents']['volume']['outline_polygon'] = make_polygon([
      (69.999, 169.999),
      (70.001, 169.999),
      (70.001, 170.001),
      (69.999, 170.001)
    ])
    mutated_subscription['extents']['volume']['altitude_upper']['value'] = 1000

    mutated_query = make_vol4(
      datetime.utcnow(), datetime.utcnow() + timedelta(seconds=10),
      0, 1000,
      circle=make_circle(70.002, 170, 400))

    self._nominal_subscription_cycle(
      original_subscription,
      original_query,
      mutated_subscription,
      mutated_query
    )


if __name__ == '__main__':
  unittest.main()
