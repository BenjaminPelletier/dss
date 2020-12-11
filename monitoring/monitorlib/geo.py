import requests
import s2sphere


def make_latlng_rect(spec: str) -> s2sphere.LatLngRect:
  coords = spec.split(',')
  if len(coords) != 4:
    raise ValueError('Expected lat,lng,lat,lng; found %d coordinates instead' % len(coords))
  lat1 = _validate_lat(coords[0])
  lng1 = _validate_lng(coords[1])
  lat2 = _validate_lat(coords[2])
  lng2 = _validate_lng(coords[3])
  p1 = s2sphere.LatLng.from_degrees(lat1, lng1)
  p2 = s2sphere.LatLng.from_degrees(lat2, lng2)
  return s2sphere.LatLngRect.from_point_pair(p1, p2)


def _validate_lat(lat: str) -> float:
  lat = float(lat)
  if lat < -90 or lat > 90:
    raise ValueError('Latitude must be in [-90, 90] range')
  return lat


def _validate_lng(lng: str) -> float:
  lng = float(lng)
  if lng < -180 or lng > 180:
    raise ValueError('Longitude must be in [-180, 180] range')
  return lng


def get_egm96_offset(lat: float, lng: float) -> float:
  # From https://earth-info.nga.mil/GandG/update/index.php?dir=wgs84&action=egm96-geoid-calc

  url = 'https://earth-info.nga.mil/nga-bin/gandg-bin/egm96-calc.cgi'
  body = {
    'LatitudeDeg': str(lat),
    'LongitudeDeg': str(lng),
    'Units': 'meters',
    'LatitudeMin': '',
    'LongitudeMin': '',
    'LatitudeSec': '',
    'LongitudeSec': '',
  }
  resp = requests.post(url, data=body)
  resp.raise_for_status()
  return float(resp.content.decode('utf-8').split(' ')[0])
