import collections
from datetime import datetime
import threading
from typing import Dict, List, Optional, Tuple
import uuid

from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
import jwt


_UNIX_EPOCH = datetime.utcfromtimestamp(0)


test_lock = threading.Lock()


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


def make_token(private_key: str, sub: str, scopes: str, issuer: str, aud: str) -> str:
  timestamp = int((datetime.utcnow() - _UNIX_EPOCH).total_seconds())
  payload = {
    'sub': sub,
    'nbf': timestamp - 1,
    'scope': scopes,
    'iss': issuer,
    'aud': aud,
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
    vol3['altitude_lower'] = make_altitude(alt0)
  if alt1 is not None:
    vol3['altitude_upper'] = make_altitude(alt1)
  vol4 = {'volume': vol3}
  if t0 is not None:
    vol4['time_start'] = make_time(t0)
  if t1 is not None:
    vol4['time_end'] = make_time(t1)
  return vol4


def make_time(t: datetime) -> Dict:
  return {
    'value': t.isoformat(),
    'format': 'RFC3339'
  }


def make_altitude(alt: float) -> Dict:
  return {
    'value': alt,
    'reference': 'W84',
    'units': 'M'
  }


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
