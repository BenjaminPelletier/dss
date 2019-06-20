"""Generate a KML file from one or more Operation JSON files.

Copyright 2018 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Python environment setup:
# pip install python-dateutil pytz lxml

import argparse
import collections
import copy
import csv
import datetime
import glob
import json
import os
import sys

from lxml import etree
import pytz
import tzlocal

import formatting

# KML Namespace
KMLNS = 'http://www.opengis.net/kml/2.2'
GXNS = 'http://www.google.com/kml/ext/2.2'
KML = '{%s}' % KMLNS
GX = '{%s}' % GXNS
NSMAP = {None: KMLNS, 'gx': GXNS}
TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
FEET_TO_METERS = 0.3048
T_MIN = datetime.datetime.min.replace(tzinfo=pytz.utc)
T_MAX = datetime.datetime.max.replace(tzinfo=pytz.utc)


def add_name(element, name):
  add_tag_value(element, KML + 'name', name)


def add_folder(parent, name):
  folder = etree.SubElement(parent, KML + 'Folder')
  add_name(folder, name)
  return folder


def add_style(doc, name, poly_color=None, poly_fill=None, poly_outline=None, line_color=None, line_width=None, icon_href=None):
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

  if icon_href is not None:
    icon_style = etree.SubElement(style, 'IconStyle')
    icon = etree.SubElement(icon_style, 'Icon')
    add_tag_value(icon, 'href', icon_href)


def add_tag_value(element, tag, value):
  sub = etree.SubElement(element, tag)
  sub.text = str(value)
  return sub


def add_polygon(placemark, latitudes, longitudes, altitudes):
  polygon = etree.SubElement(placemark, KML + 'Polygon')
  add_tag_value(polygon, 'altitudeMode', 'absolute')

  make_csv = lambda tup: ','.join([str(coord) for coord in tup])
  coord_sets = [make_csv(tup) for tup in zip(longitudes, latitudes, altitudes)]
  if coord_sets[0] != coord_sets[-1]:
    coord_sets.append(coord_sets[0])
  coordinates = ' '.join(coord_sets)
  boundary = etree.SubElement(polygon, KML + 'outerBoundaryIs')
  ring = etree.SubElement(boundary, KML + 'LinearRing')
  add_tag_value(ring, 'coordinates', coordinates)

  return polygon


def add_volume(folder, volume, name, offset, style):
  start_time = volume['effective_time_begin']
  end_time = volume['effective_time_end']
  alt0 = volume['min_altitude']['altitude_value'] * FEET_TO_METERS + offset
  alt1 = volume['max_altitude']['altitude_value'] * FEET_TO_METERS + offset

  pm = etree.SubElement(folder, KML + 'Placemark')
  add_name(pm, name)
  add_tag_value(pm, 'styleUrl', '#' + style)
  timespan = etree.SubElement(pm, 'TimeSpan')
  add_tag_value(timespan, 'begin', start_time.strftime(TIME_FORMAT))
  add_tag_value(timespan, 'end', end_time.strftime(TIME_FORMAT))
  root = etree.SubElement(pm, KML + 'MultiGeometry')

  coords = volume['operation_geography']['coordinates'][0]

  # Create bottom of volume
  lng, lat = zip(*coords)
  alt = [alt0] * len(lat)
  add_polygon(root, lat, lng, alt)

  # Create top of volume
  lat = list(reversed(lat))
  lng = list(reversed(lng))
  alt = [alt1] * len(lat)
  add_polygon(root, lat, lng, alt)

  # Create sides of volume
  for i0 in range(len(coords)):
    i1 = (i0 + 1) % len(coords)
    alt = [alt0, alt1, alt1, alt0]
    lng, lat = zip(*[coords[i] for i in (i1, i1, i0, i0)])
    add_polygon(root, lat, lng, alt)

  return pm


def add_track(folder, telemetry_points, name):
  pm = etree.SubElement(folder, KML + 'Placemark')
  add_name(pm, name)
  add_tag_value(pm, 'styleUrl', '#track')
  track = etree.SubElement(pm, GX + 'Track')
  add_tag_value(track, 'altitudeMode', 'absolute')
  for telemetry in telemetry_points:
    add_tag_value(track, 'when', formatting.timestamp(telemetry.timestamp))
  for telemetry in telemetry_points:
    add_tag_value(track, GX + 'coord', '%.6f %.6f %.2f' % (telemetry.lng, telemetry.lat, telemetry.alt))


def main(argv):
  del argv

  parser = argparse.ArgumentParser(description='Generate a KML file from one or more Operation JSON files.')
  parser.add_argument('updates', metavar='PATH_PATTERN', nargs='+', help='Path glob(s) containing `monitor` output')
  parser.add_argument('--kml_file', dest='kml_file', default='ops.kml', help='Path of KML file to create',
                      metavar='FILENAME')
  parser.add_argument('--volumes_after', dest='volumes_after', default='', metavar='TIMESTAMP',
                      help='If specified, do not include any Operations with volumes entirely before this time')
  parser.add_argument('--volumes_before', dest='volumes_before', default='', metavar='TIMESTAMP',
                      help='If specified, do not include any Operations with volumes entirely after this time')
  parser.add_argument('--submitted_after', dest='submitted_after', default='', metavar='TIMESTAMP',
                      help='If specified, do not include any Operations with submit_time before this time')
  parser.add_argument('--submitted_before', dest='submitted_before', default='', metavar='TIMESTAMP',
                      help='If specified, do not include any Operations with submit_time after this time')
  parser.add_argument('--updated_after', dest='updated_after', default='', metavar='TIMESTAMP',
                      help='If specified, do not include any Operations with update_time before this time')
  parser.add_argument('--updated_before', dest='updated_before', default='', metavar='TIMESTAMP',
                      help='If specified, do not include any Operations with update_time after this time')
  parser.add_argument(
    '--altitude_offset', dest='altitude_offset', type=float, default=32.9, metavar='METERS',
    help='The adjustment that should be applied to WGS84 altitudes for them to be displayed in an EGM96 system. If '
         'WGS84 altitude is lower than EGM96, this value should be positive. If the geoid height is negative, this '
         'value should be positive.  Near 37.197, -80.571, this offset should be about +32.59.')
  parser.add_argument('--telemetry', dest='telemetry', default='', metavar='CSV_FILENAME',
                      help='A telemetry CSV file containing columns GUFI,Timestamp,Latitude (degrees),Longitude '
                           '(degrees),Altitude (meters WGS84)')
  parser.add_argument('--uss_with_telemetry', dest='uss_with_telemetry', default='', metavar='USS_NAMES',
                      help='Comma-separated list of USSs that have telemetry')
  parser.add_argument('--include_unflown_flights', dest='include_unflown_flights', action='store_true', default=False,
                      help='If specified, include flights from USSs with telemetry in general even when those specific '
                           'flights do not have telemetry')
  args = parser.parse_args()

  volumes_after = formatting.parse_timestamp(args.volumes_after) if args.volumes_after else T_MIN
  volumes_before = formatting.parse_timestamp(args.volumes_before) if args.volumes_before else T_MAX
  submitted_after = formatting.parse_timestamp(args.submitted_after) if args.submitted_after else T_MIN
  submitted_before = formatting.parse_timestamp(args.submitted_before) if args.submitted_before else T_MAX
  updated_after = formatting.parse_timestamp(args.updated_after) if args.updated_after else T_MIN
  updated_before = formatting.parse_timestamp(args.updated_before) if args.updated_before else T_MAX
  uss_with_telemetry = set(args.uss_with_telemetry.split(','))
  include_unflown_flights = args.include_unflown_flights

  # Read operation and grid updates
  op_updates = {}
  grid_updates = []
  for pattern in args.updates:
    for filename in sorted(glob.glob(pattern)):
      with open(filename) as f:
        update = json.loads(f.read())

      update['filename'] = filename

      if 'gufi' in update:
        # Update is an operation update
        op = update
        op['submit_time'] = formatting.parse_timestamp(op['submit_time'])
        op['update_time'] = formatting.parse_timestamp(op['update_time'])
        for vol in op['operation_volumes']:
          vol['effective_time_begin'] = formatting.parse_timestamp(vol['effective_time_begin'])
          vol['effective_time_end'] = formatting.parse_timestamp(vol['effective_time_end'])
          vol['original_time_begin'] = True
        start_time = min(vol['effective_time_begin'] for vol in op['operation_volumes'])
        end_time = max(vol['effective_time_end'] for vol in op['operation_volumes'])
        op['start_time'] = start_time
        op['end_time'] = end_time
        if (end_time < volumes_after or start_time > volumes_before or
          op['submit_time'] < submitted_after or op['submit_time'] > submitted_before or
          op['update_time'] < updated_after or op['update_time'] > updated_before):
          print('Skipping operation update ' + filename)
          continue
        else:
          updates = op_updates.get(op['gufi'], [])
          updates.append(op)
          op_updates[op['gufi']] = updates

      elif 'sync_token' in update:
        # Update is a grid update
        timestamp = formatting.parse_timestamp(update['data']['timestamp'])
        timestamp_filename = tzlocal.get_localzone().localize(datetime.datetime.strptime(
          os.path.split(filename)[1][0:len('YYYYMMDD_HHMMSS')], '%Y%m%d_%H%M%S')).astimezone(pytz.utc)
        if (timestamp_filename - timestamp).total_seconds() > 15:
          timestamp = timestamp_filename
        update['data']['timestamp'] = timestamp
        for uvr in update['data']['uvrs']:
          uvr['effective_time_begin'] = formatting.parse_timestamp(uvr['effective_time_begin'])
          uvr['effective_time_end'] = formatting.parse_timestamp(uvr['effective_time_end'])
        grid_updates.append(update)
  grid_updates = list(sorted(grid_updates, key=lambda update: update['data']['version']))

  # Read telemetry
  Telemetry = collections.namedtuple('Telemetry', ('timestamp', 'lat', 'lng', 'alt'))
  telemetry_by_gufi = {}
  if args.telemetry:
    with open(args.telemetry) as f:
      reader = csv.reader(f)
      for row in reader:
        telemetry = Telemetry(formatting.parse_timestamp(row[1]),
                              float(row[2]), float(row[3]), float(row[4]) + args.altitude_offset)
        gufi = row[0]
        if gufi in telemetry_by_gufi:
          telemetry_by_gufi[gufi].append(telemetry)
        else:
          telemetry_by_gufi[gufi] = [telemetry]
    for gufi in telemetry_by_gufi:
      telemetry_by_gufi[gufi] = list(sorted(telemetry_by_gufi[gufi], key=lambda t: t.timestamp))


  # Find UVRs
  uvrs = []
  active_uvrs = {}
  for grid_update in grid_updates:
    timestamp = grid_update['data']['timestamp']

    # Identify new UVRs
    current_uvrs = set()
    for uvr_declaration in grid_update['data']['uvrs']:
      current_uvrs.add(uvr_declaration['message_id'])
      if uvr_declaration['message_id'] not in active_uvrs:
        uvr = copy.deepcopy(uvr_declaration)
        uvr['operation_geography'] = uvr['geography']
        uvr['time_announced'] = timestamp
        if uvr['effective_time_begin'] < timestamp:
          uvr['effective_time_begin'] = timestamp
        uvrs.append(uvr)
        active_uvrs[uvr['message_id']] = uvr

    # Identify cancelled UVRs
    cancelled_uvrs = set(active_uvrs.keys()) - current_uvrs
    for message_id in cancelled_uvrs:
      uvr = active_uvrs[message_id]
      if uvr['effective_time_end'] > timestamp:
        uvr['effective_time_end'] = timestamp
      del active_uvrs[message_id]

  # Determine the lifespans of operations according to the grid
  OpTimebounds = collections.namedtuple('OpTimebounds', ('first_seen', 'disappeared'))
  op_grid_timebounds = {}
  for update in grid_updates:
    timestamp = update['data']['timestamp']

    gufis = set()
    for operator in update['data']['operators']:
      for operation in operator['operations']:
        gufi = operation['gufi']
        gufis.add(gufi)
        if gufi not in op_grid_timebounds:
          op_grid_timebounds[gufi] = OpTimebounds(timestamp, T_MAX)

    for gufi in op_grid_timebounds:
      if gufi not in gufis and timestamp < op_grid_timebounds[gufi].disappeared:
        op_grid_timebounds[gufi] = OpTimebounds(op_grid_timebounds[gufi].first_seen, timestamp)

  # Construct synthesis of volumes per operation based on timing of updates
  ops = []
  for gufi, updates in op_updates.items():
    updates = list(sorted(updates, key=lambda update_item: update_item['update_time']))
    synth_op = copy.deepcopy(updates[0])
    synth_op['operation_volumes'] = []
    future_vols = {}
    for update in updates:
      update_time = update['update_time']
      synth_vols = []

      # Include only existing volumes that started before this update, trimmed to this update
      for vol in synth_op['operation_volumes']:
        if vol['effective_time_begin'] >= update_time and vol['name'] in future_vols:
          # Truncate the anticipation of future volume at this point
          future_vol = future_vols[vol['name']]
          future_vol['effective_time_end'] = update_time
          continue
        if vol['effective_time_end'] > update_time:
          vol['effective_time_end'] = update_time
        synth_vols.append(vol)

      # Incorporate volumes from new update
      for vol in update['operation_volumes']:
        vol['future'] = False
        if vol['effective_time_end'] <= update_time:
          # Do not include volumes from this update that ended in the past
          continue
        vol['name'] = str(vol['ordinal']) + ' ' + datetime.datetime.strftime(update['update_time'], '%H:%M:%S')
        if vol['effective_time_begin'] < update_time:
          # Trim current volumes to start at this update
          vol['effective_time_begin'] = update_time
          vol['original_time_begin'] = False
        else:
          # A future volume to anticipate this volume starting in the future
          future_vol = copy.deepcopy(vol)
          future_vol['future'] = True
          future_vol['effective_time_begin'] = update_time
          future_vol['effective_time_end'] = vol['effective_time_begin']
          future_vols[vol['name']] = future_vol
        synth_vols.append(vol)

      synth_vols.extend(future_vols.values())
      synth_op['operation_volumes'] = synth_vols
      synth_op['announce_time'] = update_time
    ops.append(synth_op)

  # Trim synthesis operations according to time in which the operations were in the grid, and snap submit_time to grid
  for op in ops:
    if op['gufi'] not in op_grid_timebounds:
      print('WARNING: %s operation %s was not found announced in any grid updates' % (op['uss_name'], op['gufi']))
      continue

    first_seen = op_grid_timebounds[op['gufi']].first_seen
    disappeared = op_grid_timebounds[op['gufi']].disappeared
    if op['start_time'] < first_seen:
      op['start_time'] = first_seen
    if op['end_time'] > disappeared:
      op['end_time'] = disappeared
    for vol in op['operation_volumes']:
      if vol['effective_time_begin'] < first_seen:
        vol['effective_time_begin'] = first_seen
      if vol['effective_time_end'] > disappeared:
        vol['effective_time_end'] = disappeared
    op['submit_time'] = first_seen

  # Delete any operations outside desired bounds
  ops = [op for op in ops if op['start_time'] < volumes_before and op['end_time'] > volumes_after]

  # Construct KML
  name = datetime.datetime.strftime(max(op['update_time'] for op in ops), '%Y%m%d_%H%M%S')
  kml = etree.Element(KML + 'kml', nsmap=NSMAP)
  doc = etree.SubElement(kml, KML + 'Document')
  add_name(doc, name)
  add_style(doc, 'op_active', line_color='#ff37d7fb', line_width=2.0, poly_color='#7d37d7fb')
  add_style(doc, 'op_future', line_color='#ff864d2b', line_width=1.0, poly_color='#00000000')
  add_style(doc, 'unflown_op_active', line_color='#306b1b7d', line_width=2.0, poly_color='#306b1b7d')
  add_style(doc, 'unflown_op_future', line_color='#306b1b7d', line_width=1.0, poly_color='#00000000')
  add_style(doc, 'uvr_active', line_color='#ff0000ff', line_width=2.0, poly_color='#800000ff')
  add_style(doc, 'uvr_future', line_color='#ff0040a0', line_width=1.0, poly_color='#300040a0')
  if telemetry_by_gufi:
    add_style(doc, 'track', line_color='99ffac59', line_width=6,
              icon_href='http://earth.google.com/images/kml-icons/track-directional/track-0.png')

  if ops:
    ops_folder = add_folder(doc, 'Operations')
    for op in sorted(ops, key=lambda op_item: op_item['submit_time']):
      if telemetry_by_gufi and op['uss_name'] in uss_with_telemetry and op['gufi'] not in telemetry_by_gufi:
        if not include_unflown_flights:
          continue
        style_prefix = 'unflown_'
      else:
        style_prefix = ''

      time_name = datetime.datetime.strftime(op['submit_time'], '%H:%M:%S')
      folder = add_folder(ops_folder, '%s %s %s' % (time_name, op['uss_name'], op['gufi']))
      for volume in op['operation_volumes']:
        if volume['effective_time_end'] >= volume['effective_time_begin']:
          if volume['future']:
            add_volume(folder, volume, 'Future ' + str(volume['name']), args.altitude_offset,
                       style_prefix + 'op_future')
          else:
            add_volume(folder, volume, volume['name'], args.altitude_offset, style_prefix + 'op_active')

      if op['gufi'] in telemetry_by_gufi:
        add_track(folder, telemetry_by_gufi[op['gufi']], 'Telemetry ' + op['gufi'])


  if uvrs:
    uvrs_folder = add_folder(doc, 'UVRs')
    for uvr in uvrs:
      if (uvr['effective_time_end'] < volumes_after or uvr['effective_time_begin'] > volumes_before or
          uvr['time_announced'] < submitted_after or uvr['time_announced'] > submitted_before or
          uvr['time_announced'] < updated_after or uvr['time_announced'] > updated_before):
        continue
      time_name = datetime.datetime.strftime(uvr['time_announced'], '%H:%M:%S')

      # Add UVR announcement
      if uvr['effective_time_begin'] > uvr['time_announced'] and uvr['effective_time_end'] > uvr['time_announced']:
        future_uvr = copy.deepcopy(uvr)
        future_uvr['effective_time_begin'] = uvr['time_announced']
        future_uvr['effective_time_end'] = min(uvr['effective_time_begin'], uvr['effective_time_end'])
        add_volume(
          uvrs_folder, future_uvr, 'Future %s %s' % (time_name, uvr['message_id']), args.altitude_offset, 'uvr_future')

      # Add active UVR
      if uvr['effective_time_end'] > uvr['effective_time_begin']:
        add_volume(uvrs_folder, uvr, '%s %s' % (time_name, uvr['message_id']), args.altitude_offset, 'uvr_active')

  # Write KML
  with open(args.kml_file, 'w') as f:
    f.write(etree.tostring(doc.getroottree(), xml_declaration=True, pretty_print=True))


if __name__ == '__main__':
  main(sys.argv)
