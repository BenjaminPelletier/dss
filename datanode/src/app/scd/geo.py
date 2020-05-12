import datetime
import json
import math
from typing import Dict, Iterable, Optional, Set

import geojson
import s2sphere

from app.dsslib import format_utils


EARTH_CIRCUMFERENCE_M = 40.075e6
RADIANS_PER_METER = 2 * math.pi / EARTH_CIRCUMFERENCE_M


class Config(object):
  min_s2_level: int
  max_s2_level: int
  def __init__(self, min_s2_level: int, max_s2_level: int):
    self.min_s2_level = min_s2_level
    self.max_s2_level = max_s2_level



class Volume4(object):
  def __init__(
      self,
      time_start: Optional[datetime.datetime],
      time_end: Optional[datetime.datetime],
      altitude_lo: Optional[float],
      altitude_hi: Optional[float],
      cells: Set[s2sphere.CellId]):
    self.time_start = time_start
    self.time_end = time_end
    self.altitude_lo = altitude_lo
    self.altitude_hi = altitude_hi
    self.cells = cells

  def contains(self, other) -> bool:
    assert isinstance(other, Volume4)
    if (other.altitude_lo < self.altitude_lo or
        other.altitude_hi > self.altitude_hi or
        other.time_start < self.time_start or
        other.time_end > self.time_end):
      return False
    my_union = s2sphere.CellUnion(self.cells)
    other_union = s2sphere.CellUnion(other.cells)
    return my_union.contains(other_union)


def combine_volume4s(vol4s: Iterable[Volume4]) -> Volume4:
  union = None
  for vol4 in vol4s:
    if union is None:
      union = Volume4(vol4.time_start, vol4.time_end, vol4.altitude_lo, vol4.altitude_hi, set(vol4.cells))
    else:
      union.time_start = vol4.time_start if vol4.time_start < union.time_start else union.time_start
      union.time_end = vol4.time_end if vol4.time_end > union.time_end else union.time_end
      union.altitude_lo = vol4.altitude_lo if vol4.altitude_lo < union.altitude_lo else union.altitude_lo
      union.altitude_hi = vol4.altitude_hi if vol4.altitude_hi > union.altitude_hi else union.altitude_hi
    union.cells = set.union(union.cells, vol4.cells)
  return union


def _get_altitude(alt_json: Dict) -> Optional[float]:
  if alt_json is None:
    return None
  if not isinstance(alt_json, dict):
    raise ValueError('altitude should be an object with `reference`, `units`, and `value` fields')
  if alt_json.get('reference', None) != 'W84':
    raise ValueError('Incorrect `reference` in altitude; expected W84')
  if alt_json.get('units', None) != 'M':
    raise ValueError('Incorrect `units` in altitude; expected M')
  return alt_json.get('value', None)


def _get_time(time_json: Dict) -> Optional[datetime.datetime]:
  if time_json is None:
    return None
  if not isinstance(time_json, dict):
    raise ValueError('time should be an object with `format` and `value` fields')
  if time_json.get('format', None) != 'RFC3339':
    raise ValueError('Incorrect `format` in time; expected RFC3339')
  return format_utils.parse_timestamp(time_json['value'])


def overlaps_time_altitude(area_of_interest: Volume4, vol4: Volume4) -> bool:
  if area_of_interest.time_start is not None and vol4.time_end < area_of_interest.time_start:
    return False
  if area_of_interest.time_end is not None and vol4.time_start > area_of_interest.time_end:
    return False
  if area_of_interest.altitude_lo is not None and vol4.altitude_hi < area_of_interest.altitude_lo:
    return False
  if area_of_interest.altitude_hi is not None and vol4.altitude_lo > area_of_interest.altitude_hi:
    return False
  return True


def expand_volume4(extents: Dict, min_s2_level: int, max_s2_level: int) -> Volume4:
  if 'volume' not in extents:
    raise ValueError('Missing `volume` in Volume3')
  volume = extents['volume']

  if ('outline_circle' in volume) == ('outline_polygon' in volume):
    raise ValueError('Expected exactly one of `outline_circle` or `outline_polygon` to be specified in Volume3')

  cells = set()
  r = s2sphere.RegionCoverer()
  r.min_level = min_s2_level
  r.max_level = max_s2_level

  if 'outline_circle' in volume:
    circle = geojson.loads(json.dumps(volume['outline_circle']))
    if not circle.is_valid:
      raise ValueError('outline_circle GeoJSON errors: ' + circle.errors())
    if circle.get('type', None) != 'Feature':
      raise ValueError('Expected `outline_circle` to have `type` Feature')

    geometry = circle.get('geometry', None)
    if geometry is None:
      raise ValueError('Missing `geometry` in outline_circle')
    if geometry.get('type', None) != 'Point':
      raise ValueError('Expected `geometry` to have `type` Point `outline_circle` `geometry`')
    coordinates = geometry.get('coordinates', [])
    if len(coordinates) != 2:
      raise ValueError('Expected 2 elements in `outline_circle` `geometry` `coordinates`')
    lng = coordinates[0]
    lat = coordinates[1]
    if lng < -180 or lng > 180:
      raise ValueError('Circle center point longitude outside [-180, 180]')
    if lat < -90 or lat > 90:
      raise ValueError('Circle center point latitude outside [-90, 90]')

    if 'properties' not in circle:
      raise ValueError('Missing `properties` in `outline_circle')
    radius = circle['properties'].get('radius', None)
    if radius is None:
      raise ValueError('Missing `radius` in `properties` of `outline_circle`')
    if radius.get('units', None) != 'M':
      raise ValueError('Expected `radius` `units` of `outline_circle` should be M')
    radius = radius.get('value', None)
    if radius is None:
      raise ValueError('Missing `radius` `value` in `outline_circle` `properties`')

    center_point = s2sphere.LatLng.from_degrees(lat, lng).to_point()
    radius_height = s2sphere.Cap.get_height_for_angle(radius * RADIANS_PER_METER)
    cap = s2sphere.Cap(center_point, radius_height)
    covering = r.get_covering(cap)
    for cell in covering:
      cells.add(cell)

  if 'outline_polygon' in volume:
    polygon = geojson.loads(json.dumps(volume['outline_polygon']))
    if not polygon.is_valid:
      raise ValueError('outline_polygon GeoJSON errors: ' + polygon.errors())
    if polygon.get('type', None) != 'Polygon':
      raise ValueError('Expected `outline_polygon` to have `type` Polygon')

    if not polygon.get('coordinates', None):
      raise ValueError('Missing `coordinates` in outline_polygon')
    if len(polygon['coordinates']) != 1:
      raise ValueError('Expected exactly one element in outline_polygon coordinates')
    coords = polygon['coordinates'][0]
    if len(coords) < 4:
      raise ValueError('Expected at least 4 elements in outline_polygon coordinates')
    if coords[0] != coords[-1]:
      raise ValueError('Expected first set of coordinates in outline_polygon to match last set')

    bounding_box = s2sphere.LatLngRect.from_point(s2sphere.LatLng.from_degrees(coords[0][1], coords[0][0]))
    for coord in coords[1:]:
      bounding_box = bounding_box.union(
        s2sphere.LatLngRect.from_point(s2sphere.LatLng.from_degrees(coord[1], coord[0])))

    covering = r.get_covering(bounding_box)
    for cell in covering:
      cells.add(cell)

  return Volume4(
    _get_time(extents.get('time_start', None)),
    _get_time(extents.get('time_end', None)),
    _get_altitude(volume.get('altitude_lower', None)),
    _get_altitude(volume.get('altitude_upper', None)),
    cells)
