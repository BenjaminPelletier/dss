"""Command a miniuss instance to perform an action.

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
# pip install djangorestframework python-dateutil pytz requests shapely tzlocal

import argparse
import datetime
import inspect
import json
import logging
import os
import requests
import sys
import uuid

from rest_framework import status
import tzlocal

import formatting
import interuss_platform

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
log = logging.getLogger('MiniUssCmd')
log.setLevel(logging.DEBUG)


def close_operation(args):
  if not args.id:
    log.error('Missing id argument')
    sys.exit(1)
  if not args.authurl:
    log.error('Missing authurl argument')
    sys.exit(1)
  if not args.authkey:
    log.error('Missing authkey argument')
    sys.exit(1)
  if not args.nodeurl:
    log.error('Missing ussurl argument')
    sys.exit(1)
  raise NotImplementedError('close_operation not yet supported')


def get_operation_info(args):
  if not args.id:
    log.error('Missing id argument')
    sys.exit(1)
  if not args.authurl:
    log.error('Missing authurl argument')
    sys.exit(1)
  if not args.authkey:
    log.error('Missing authkey argument')
    sys.exit(1)
  if not args.ussurl:
    log.error('Missing ussurl argument')
    sys.exit(1)
  token_manager = interuss_platform.TokenManager(args.authurl, args.authkey)
  url = os.path.join(args.ussurl, 'operations', args.id)
  headers = {'Authorization': 'Bearer ' + token_manager.get_token('utm.nasa.gov_write.operation')}
  response = requests.get(url, headers=headers)
  response.raise_for_status()
  log.info('Operation info: ' + json.dumps(response.json(), indent=2))


def add_uvr(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  if not args.json_file:
    log.error('Missing json_file argument')
    sys.exit(1)
  log.info('Adding UVR')

  with open(args.json_file) as f:
    uvr_source = f.read()
  message_id = json.loads(uvr_source).get('message_id', None)
  if not message_id:
    if args.id:
      message_id = args.id
    else:
      message_id = str(uuid.uuid4())
      log.info('Setting message ID to ' + message_id)

  # Make sure UVR doesn't already exist
  url = os.path.join(args.miniuss_url, 'client', 'uvr', message_id)
  response = requests.get(url)
  if response.status_code != status.HTTP_404_NOT_FOUND:
    log.error('UVR %s may already exist (code %d when queried)', message_id, response.status_code)
    sys.exit(1)

  uvr_source = uvr_source.replace('{{start_time}}', formatting.timestamp(args.start_time))
  uvr_source = uvr_source.replace('{{end_time}}', formatting.timestamp(args.end_time))
  uvr = json.loads(uvr_source)
  uvr['message_id'] = message_id

  response = requests.put(url, json=uvr, headers={'Authorization': args.control_authorization})
  if response.status_code == 200:
    response_json = response.json()
    min_time = formatting.parse_timestamp(response_json['uvr']['effective_time_begin'])
    max_time = formatting.parse_timestamp(response_json['uvr']['effective_time_end'])
    log.info('Success adding UVR %s from %s to %s (current time %s)', response_json['uvr']['message_id'],
             min_time, max_time, formatting.timestamp(datetime.datetime.utcnow()))
  else:
    log.error('Error %d while trying to add UVR %s: %s', response.status_code, message_id, response.content)


def remove_uvr(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  if not args.json_file and not args.id:
    log.error('UVR not specified (missing json_file and id arguments)')
    sys.exit(1)
  log.info('Removing UVR')
  if args.id:
    message_id = args.id
    uvr = None
  else:
    with open(args.json_file) as f:
      uvr = json.loads(f.read())
    message_id = uvr['message_id']

  url = os.path.join(args.miniuss_url, 'client', 'uvr', message_id)
  response = requests.delete(url, headers={'Authorization': args.control_authorization}, json=uvr)
  if response.status_code == 204:
    log.info('Success deleting UVR %s', message_id)
  else:
    log.error('Error %d while trying to delete UVR %s: %s', response.status_code, message_id, response.content)


def remove_operator_entry(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  if not args.slippy_cells:
    log.error('Missing slippy_cells argument')
    sys.exit(1)
  url = os.path.join(args.miniuss_url, 'client', 'operator_entries')
  response = requests.delete(url, json=args.slippy_cells.split(','),
                             headers={'Authorization': args.control_authorization})
  response.raise_for_status()
  log.info('miniuss outcomes for attempts to remove operator entries:\n' + json.dumps(response.json(), indent=2))


def list_alwayslisten(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  url = os.path.join(args.miniuss_url, 'client', 'alwayslisten')
  response = requests.get(url)
  response.raise_for_status()
  log.info('miniuss always listening to cells {%s}', ', '.join(response.json()))


def set_alwayslisten(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  if not args.slippy_cells:
    log.error('Missing slippy_cells argument')
    sys.exit(1)
  url = os.path.join(args.miniuss_url, 'client', 'alwayslisten')
  response = requests.put(url, json=args.slippy_cells.split(','),
                          headers={'Authorization': args.control_authorization})
  response.raise_for_status()
  if response.status_code == status.HTTP_204_NO_CONTENT:
    log.info('miniuss will now always listen to announcements in cells ' + args.slippy_cells)


def list_operations(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  response = requests.get(args.miniuss_url)
  response.raise_for_status()
  operations = response.json()['operations']
  if operations:
    log.info('Current operations exposed by miniuss:\n' + '\n'.join(operations))
  else:
    log.info('miniuss not currently exposing any operations')


def add_operation(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  if not args.json_file:
    log.error('Missing json_file argument')
    sys.exit(1)
  log.info('Adding operation')

  with open(args.json_file) as f:
    op_source = f.read()
  gufi = json.loads(op_source).get('gufi', None)
  if not gufi:
    if args.id:
      gufi = args.id
    else:
      gufi = str(uuid.uuid4())
      log.info('Setting GUFI to ' + gufi)

  # Make sure operation doesn't already exist
  url = os.path.join(args.miniuss_url, 'client', 'operation', gufi)
  response = requests.get(url)
  if response.status_code != status.HTTP_404_NOT_FOUND:
    log.error('Operation %s may already exist (code %d when queried)', gufi, response.status_code)
    sys.exit(1)

  op_source = op_source.replace('{{start_time}}', formatting.timestamp(args.start_time))
  op_source = op_source.replace('{{end_time}}', formatting.timestamp(args.end_time))
  op = json.loads(op_source)
  op['submit_time'] = formatting.timestamp(datetime.datetime.utcnow())
  op['update_time'] = op['submit_time']
  op['gufi'] = gufi

  response = requests.put(url, json=op, headers={'Authorization': args.control_authorization})
  if response.status_code == 200:
    response_json = response.json()
    times = [(formatting.parse_timestamp(v['effective_time_begin']),
              formatting.parse_timestamp(v['effective_time_end'])) for v in response_json['operation_volumes']]
    min_time = formatting.timestamp(min(t[0] for t in times))
    max_time = formatting.timestamp(max(t[1] for t in times))
    log.info('Success adding operation %s from %s to %s (current time %s)', response_json['gufi'], min_time, max_time,
             formatting.timestamp(datetime.datetime.utcnow()))
  else:
    log.error('Error %d while trying to add operation %s: %s', response.status_code, gufi, response.content)


def remove_operation(args):
  if not args.miniuss_url:
    log.error('Missing miniuss_url argument')
    sys.exit(1)
  if not args.json_file and not args.id:
    log.error('Operation not specified (missing json_file and id arguments)')
    sys.exit(1)
  log.info('Removing operation')
  if args.id:
    gufi = args.id
  else:
    with open(args.json_file) as f:
      gufi = json.loads(f.read())['gufi']

  url = os.path.join(args.miniuss_url, 'client', 'operation', gufi)
  response = requests.delete(url, headers={'Authorization': args.control_authorization})
  if response.status_code == 204:
    log.info('Success deleting operation %s', gufi)
  else:
    log.error('Error %d while trying to delete operation %s: %s', response.status_code, gufi, response.content)


def main(argv):
  del argv

  parser = argparse.ArgumentParser(description='Perform a query or manipulation on a miniuss server')
  parser.add_argument('command', metavar='CMD', help='Command to execute')
  parser.add_argument('--miniuss_url', dest='miniuss_url', default=os.getenv('MINIUSS_URL', 'http://127.0.0.1'),
                      help='Base URL of miniuss instance to control', metavar='URL')
  parser.add_argument('--json_file', dest='json_file', default='', help='JSON definition of operation, UVR, etc')
  parser.add_argument('--id', dest='id', default='', help='GUFI of operation or message ID of UVR to manipulate')
  parser.add_argument('--start_time', dest='start_time', default=datetime.datetime.now().strftime('%H:%M'),
                      help='When the operation will start')
  parser.add_argument('--end_time', dest='end_time', default='', help='When the operation will end')
  parser.add_argument('--duration', dest='duration', type=float, default=10,
                      help='Number of minutes operation will last')
  parser.add_argument('--authorization', dest='control_authorization',
                      default=os.getenv('MINIUSS_CONTROL_AUTHORIZATION', 'miniuss'),
                      help='Content of Authorization header required to access control endpoints',
                      metavar='HEADERVALUE')
  parser.add_argument('--slippycells', dest='slippy_cells', default='',
                      help=('Comma-separated list of Slippy cells like 10/282/397'), metavar='CELLS')

  parser.add_argument('--nodeurl', dest='nodeurl',
                      default=os.getenv('MINIUSS_NODEURL', 'https://node3.upp.interussplatform.com:8121'),
                      help='Base URL of InterUSS Platform data node', metavar='URL')
  parser.add_argument('--authurl', dest='authurl',
                      default=os.getenv('MINIUSS_AUTHURL', 'https://uas-api.faa.gov/fimsAuthServer/oauth/token?grant_type=client_credentials'),
                      help='URL at which to retrieve access tokens', metavar='URL')
  parser.add_argument('--authkey', dest='authkey', default=os.environ.get('AUTH_KEY', None),
                      help='Base64-encoded username and password to pass to the OAuth server as '
                           'Basic XXX in the Authentication header. Defaults to AUTH_KEY '
                           'environment variable if defined',
                      metavar='AUTH_KEY')
  parser.add_argument('--ussurl', dest='ussurl', default='https://wing-prod-uss.googleapis.com/tcl4',
                      help='Base URL of USS to interact with', metavar='URL')
  args = parser.parse_args()

  # Compute effective time bounds, replacing supplied arguments
  now = tzlocal.get_localzone().localize(datetime.datetime.now())
  start_time = datetime.datetime.strptime(args.start_time, '%H:%M')
  start_time = now.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
  if args.end_time:
    end_time = datetime.datetime.strptime(args.end_time, '%H:%M')
    end_time = now.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)
  else:
    end_time = start_time + datetime.timedelta(minutes=args.duration)
  args.start_time = start_time
  args.end_time = end_time

  # Find and run appropriate function
  success = False
  for name, op in inspect.getmembers(sys.modules[__name__]):
    if name == args.command and inspect.isfunction(op):
      op(args)
      success = True
  if not success:
    log.error('Invalid command: ' + args.command)


if __name__ == '__main__':
  main(sys.argv)
