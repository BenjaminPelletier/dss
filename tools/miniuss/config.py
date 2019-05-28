"""Configuration options for miniuss.

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

from optparse import OptionParser
import os


def parse_options(argv):
  """Parses desired options from the command line and starts operations.

  Uses the command line parameters as argv, which can be altered as needed for
  testing.

  Args:
    argv: Command line parameters
  Returns:
    Options structure
  """
  parser = OptionParser(usage='usage: %prog [options]')
  parser.add_option(
    '--server',
    dest='server',
    default=os.getenv('MINIUSS_SERVER', '127.0.0.1'),
    help='Specific server name to use on this machine',
    metavar='SERVER')
  parser.add_option(
    '--port',
    dest='port',
    default=os.getenv('MINIUSS_PORT', '5000'),
    help='Specific port to use on this machine',
    metavar='PORT')
  parser.add_option(
    '--nodeurl',
    dest='nodeurl',
    default=os.getenv('MINIUSS_NODEURL',
                      'https://staging.upp.interussplatform.com:8121'),
    help='Base URL of InterUSS Platform data node',
    metavar='URL')
  parser.add_option(
    '--authurl',
    dest='authurl',
    default=os.getenv('MINIUSS_AUTHURL',
                      'https://auth.staging.interussplatform.com:8121/oauth/token?grant_type=client_credentials'),
    help='URL at which to retrieve access tokens',
    metavar='URL')
  parser.add_option(
    '--baseurl',
    dest='baseurl',
    default=os.getenv('MINIUSS_BASEURL', 'http://localhost:5000'),
    help='Base URL for public_portal_endpoint and flight_info_endpoint',
    metavar='URL')
  parser.add_option(
    '-k', '--authpublickey',
    dest='authpublickey',
    default=os.getenv('MINIUSS_AUTHPUBLICKEY',
                      'https://auth.staging.interussplatform.com:8121/key'),
    help='URL at which to retrieve the public key to validate access tokens, '
         'or the public key itself',
    metavar='URL|KEY')
  parser.add_option(
    '-u', '--username',
    dest='username',
    default=os.getenv('MINIUSS_USERNAME', 'uss1.test'),
    help='Username for retrieving access tokens',
    metavar='USERNAME')
  parser.add_option(
    '-p', '--password',
    dest='password',
    default=os.getenv('MINIUSS_PASSWORD', ''),
    help='Password for retrieving access tokens',
    metavar='PASSWORD')
  parser.add_option(
    '--zoom',
    dest='zoom',
    default=os.getenv('MINIUSS_ZOOM', '10'),
    help='InterUSS Platform zoom level',
    metavar='ZOOM')
  parser.add_option(
    '-a', '--authorization',
    dest='control_authorization',
    default=os.getenv('MINIUSS_CONTROL_AUTHORIZATION', 'miniuss'),
    help='Content of Authorization header required to access control endpoints',
    metavar='HEADERVALUE')
  parser.add_option(
    '--alwayslisten',
    dest='always_listen',
    default=os.getenv('MINIUSS_ALWAYS_LISTEN', '10/282/397'),
    help='Comma-separated grid cell(s) in which to always have a operator entry',
    metavar='CELLS')
  parser.add_option(
    '--minlistentime',
    dest='min_listen_time',
    default=os.getenv('MINIUSS_MIN_LISTEN_TIME', '2019-03-01T00:00:00.000Z'),
    help='minimum_operation_timestamp for observer-only cells',
    metavar='TIMESTAMP')
  parser.add_option(
    '--maxlistentime',
    dest='max_listen_time',
    default=os.getenv('MINIUSS_MIN_LISTEN_TIME', '2019-07-01T00:00:00.000Z'),
    help='maximum_operation_timestamp for observer-only cells',
    metavar='TIMESTAMP')
  (options, args) = parser.parse_args(argv)
  del args

  return options
