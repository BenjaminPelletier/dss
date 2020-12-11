import enum
import numbers
import six

from lxml import etree


KMLNS = 'http://www.opengis.net/kml/2.2'
KML = '{%s}' % KMLNS
NSMAP = {None: KMLNS}
TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


class AltitudeMode(enum.Enum):
  CLAMP = 'clampToGround'
  AGL = 'relativeToGround'
  WGS84 = 'absolute'


def make_document(name=None):
  kml = etree.Element(KML + 'kml', nsmap=NSMAP)
  doc = etree.SubElement(kml, KML + 'Document')
  if name:
    add_name(doc, name)
  return doc


def url_safe(unsafe: str) -> str:
  return six.moves.urllib.parse.quote(unsafe)


def add_tag_value(element, tag, text):
  if not isinstance(text, six.string_types):
    text = str(text)
  element = etree.SubElement(element, tag)
  element.text = text.encode('utf-8').decode('utf-8')
  return element


def add_name(element, name):
  return add_tag_value(element, KML + 'name', name)


def add_folder(root, name):
  folder = etree.SubElement(root, KML + 'Folder')
  add_name(folder, name)
  return folder


def add_style(doc, name, poly_color=None, poly_fill=None, poly_outline=None,
             line_color=None, line_width=None, icon=None, icon_color=None,
             icon_scale=None):
  style = etree.SubElement(doc, 'Style')
  style.attrib['id'] = name
  if poly_fill is not None or poly_outline is not None or poly_color:
    ps = etree.SubElement(style, 'PolyStyle')
    if poly_color:
      add_tag_value(ps, KML + 'color', poly_color)
    if poly_fill is not None:
      add_tag_value(ps, KML + 'fill', int(poly_fill))
    if poly_outline is not None:
      add_tag_value(ps, KML + 'outline', int(poly_outline))

  if line_color or line_width is not None:
    ls = etree.SubElement(style, 'LineStyle')
    if line_color:
      add_tag_value(ls, KML + 'color', line_color)
    if line_width is not None:
      add_tag_value(ls, KML + 'width', line_width)

  if icon:
    ist = etree.SubElement(style, KML + 'IconStyle')
    ic = etree.SubElement(ist, KML + 'Icon')
    add_tag_value(ic, 'href', icon)

    if icon_scale is not None:
      add_tag_value(ist, 'scale', icon_scale)
    if icon_color is not None:
      add_tag_value(ist, 'color', icon_color)

  return style


def add_coords(element, lat, lng, altitude):
  if isinstance(lat, numbers.Number):
    coord_string = '%g,%g,%g' % (lng, lat, altitude)
  else:
    coord_string = ' '.join('%g,%g,%g' % tup for tup in zip(lng, lat, altitude))
  return add_tag_value(element, KML + 'coordinates', coord_string)


def add_altitude_mode(node, altitude_mode=AltitudeMode.AGL):
  add_tag_value(node, 'altitudeMode', altitude_mode)


def apply_timespan(element, begin=None, end=None):
  if begin is None and end is None:
    return

  timespan = etree.SubElement(element, 'TimeSpan')
  if begin is not None:
    add_tag_value(timespan, 'begin', begin.strftime(TIME_FORMAT))
  if end is not None:
    add_tag_value(timespan, 'end', end.strftime(TIME_FORMAT))


def apply_style(element, style):
  if style is not None:
    add_tag_value(element, 'styleUrl', '#' + url_safe(style))


def add_multi_geometry(root):
  return etree.SubElement(root, KML + 'MultiGeometry')


def add_point(folder, name, lat, lng, style=None, altitude=None,
             altitude_mode=AltitudeMode.AGL, extrude=False, description=None):
  pm = etree.SubElement(folder, KML + 'Placemark')
  add_name(pm, name)
  point = etree.SubElement(pm, KML + 'Point')
  add_coords(point, lat, lng, altitude or 0)
  if altitude is not None:
    add_altitude_mode(point, altitude_mode)
    if extrude:
      add_tag_value(point, 'extrude', '1')
  if style is not None:
    add_tag_value(pm, 'styleUrl', '#' + url_safe(style))
  if description is not None:
    add_tag_value(pm, 'description', description)
  return pm


def add_line_string(folder, latitudes, longitudes, altitudes=None,
                    extrude=False, name=None, style=None):
  n = len(latitudes)
  assert len(longitudes) == n
  if altitudes is not None:
    assert len(altitudes) == n

  pm = etree.SubElement(folder, KML + 'Placemark')
  if name:
    add_name(pm, name)
  if style is not None:
    add_tag_value(pm, 'styleUrl', '#' + url_safe(style))
  ls = etree.SubElement(pm, KML + 'LineString')
  if not altitudes:
    altitudes = [0] * n
    add_tag_value(ls, 'tessellate', '1')
  else:
    add_altitude_mode(ls, AltitudeMode.WGS84)
    if extrude:
      add_tag_value(ls, 'extrude', '1')

  make_csv = lambda tup: ','.join([str(coord) for coord in tup])
  coord_sets = [make_csv(tup) for tup in zip(longitudes, latitudes, altitudes)]
  coordinates = ' '.join(coord_sets)
  add_tag_value(ls, 'coordinates', coordinates)

  return pm


def add_polygon_geometry(placemark, latitudes, longitudes, altitudes=None,
                         tessellate=True, altitude_mode=AltitudeMode.AGL):
  polygon = etree.SubElement(placemark, KML + 'Polygon')
  if tessellate:
    add_tag_value(polygon, 'tessellate', '1')

  n = len(latitudes)
  assert len(longitudes) == n
  if altitudes:
    add_altitude_mode(polygon, altitude_mode)
  else:
    altitudes = [0] * n

  make_csv = lambda tup: ','.join([str(coord) for coord in tup])
  coord_sets = [make_csv(tup) for tup in zip(longitudes, latitudes, altitudes)]
  if coord_sets[0] != coord_sets[-1]:
    coord_sets.append(coord_sets[0])
  coordinates = ' '.join(coord_sets)
  boundary = etree.SubElement(polygon, KML + 'outerBoundaryIs')
  ring = etree.SubElement(boundary, KML + 'LinearRing')
  add_tag_value(ring, 'coordinates', coordinates)

  return polygon


def add_polygon(folder, latitudes, longitudes, altitudes=None, name=None, style=None):
  pm = etree.SubElement(folder, KML + 'Placemark')
  if name:
    add_name(pm, name)
  if style is not None:
    add_tag_value(pm, 'styleUrl', '#' + url_safe(style))
  add_polygon_geometry(pm, latitudes, longitudes, altitudes)
  return pm


def add_volume(folder, volume, name, offset=0, style=None,
              altitude_mode=AltitudeMode.WGS84):
  start_time = volume.get('start_time')
  end_time = volume.get('end_time')

  alt0 = volume['alt_lo'] + offset
  alt1 = volume['alt_hi'] + offset

  pm = etree.SubElement(folder, KML + 'Placemark')
  add_name(pm, name)
  apply_style(pm, style)
  apply_timespan(pm, start_time, end_time)
  root = add_multi_geometry(pm)

  # Create bottom of volume
  vertices = volume['outline']
  lat, lng = list(zip(*vertices))
  alt = [alt0] * len(lat)
  add_polygon_geometry(root, lat, lng, alt, tessellate=altitude_mode != AltitudeMode.WGS84, altitude_mode=altitude_mode)

  # Create top of volume
  lat = list(reversed(lat))
  lng = list(reversed(lng))
  alts = [alt1] * len(lat)
  add_polygon_geometry(root, lat, lng, alts, tessellate=False, altitude_mode=altitude_mode)

  # Create sides of volume
  alt = [alt0, alt1, alt1, alt0]
  for i0 in range(len(vertices)):
    i1 = (i0 + 1) % len(vertices)
    side_vertices = [vertices[i] for i in (i0, i0, i1, i1)]
    lat, lng = list(zip(*side_vertices))
    add_polygon_geometry(root, lat, lng, alt, tessellate=False, altitude_mode=altitude_mode)

  return pm


def to_kml_string(doc, pretty_print=False):
  return etree.tostring(doc.getroottree(), xml_declaration=True, pretty_print=pretty_print)
