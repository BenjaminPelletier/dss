"""Test of the InterUSS Platform auth server."""
from datetime import datetime
import hashlib
import json
import jwt
import os
import shutil
import subprocess
import tempfile
import time
import unittest

import requests


# Note that openssl must be installed on the system to use this test.


BASE_URL = 'http://127.0.0.1:8210'


class InterUSSAuthServerTestCase(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    cls.path = tempfile.mkdtemp()

    private_key_file = os.path.join(cls.path, 'private.pem')
    subprocess.call(
      ('openssl genrsa -out %s 2048' % private_key_file).split(' '))

    public_key_file = os.path.join(cls.path, 'public.pem')
    subprocess.call(
      ('openssl rsa -in %s -outform PEM -pubout -out %s'
       % (private_key_file, public_key_file)).split(' '))

    roster_file = os.path.join(cls.path, 'roster.txt')
    cls.users = {
      'myuss.com': 'uss',
      'other.com': 'other',
    }
    scopes = ' '.join(('interuss.org_operators.read',
                       'interuss.org_operators.write'))
    with open(roster_file, 'w') as f:
      for username, password in cls.users.items():
        password_hash = hashlib.sha256(('InterUSS Project %s %s InterUSS Project' % (username, password)).encode('utf-8')).hexdigest()
        f.write(','.join((username, password_hash, scopes)) + '\n')

    os.environ['INTERUSS_AUTH_SERVER'] = '127.0.0.1'
    os.environ['INTERUSS_AUTH_PORT'] = '8210'
    os.environ['INTERUSS_AUTH_VERBOSE'] = 'true'
    os.environ['INTERUSS_AUTH_PUBLIC_KEY'] = public_key_file
    os.environ['INTERUSS_AUTH_PRIVATE_KEY'] = private_key_file
    os.environ['INTERUSS_AUTH_ROSTER'] = roster_file
    os.environ['INTERUSS_AUTH_ISSUER'] = 'issuer.com'
    os.environ['INTERUSS_AUTH_EXPIRATION'] = '2'

    cls.app = subprocess.Popen('exec python auth_server.py', shell=True)
    time.sleep(1)

  @classmethod
  def tearDownClass(cls):
    cls.app.kill()
    shutil.rmtree(cls.path)

  def testStatus(self):
    result = requests.get(BASE_URL + '/status')
    self.assertEqual(200, result.status_code)
    self.assertIn(b'OK', result.content)
    result = requests.get(BASE_URL)
    self.assertEqual(200, result.status_code)
    self.assertIn(b'OK', result.content)

  def testGetKey(self):
    result = requests.get(BASE_URL + '/key')
    self.assertEqual(200, result.status_code)
    self.assertIn(b'PUBLIC KEY', result.content)

  def testMissingAuthorization(self):
    result = requests.post(BASE_URL + '/oauth/token',
                           {'grant_type': 'client_credentials',
                            'aud': 'receiver.com'})
    self.assertEqual(401, result.status_code)

  def testBadAuthorization(self):
    result = requests.post(BASE_URL + '/oauth/token',
                           {'grant_type': 'client_credentials',
                            'aud': 'receiver.com'},
                           auth=('myuss.com', 'wrong'))
    self.assertEqual(401, result.status_code)

    result = requests.post(BASE_URL + '/oauth/token',
                           {'grant_type': 'client_credentials',
                            'aud': 'receiver.com'},
                           auth=('nonexistent', 'uss'))
    self.assertEqual(401, result.status_code)

  def testMissingGrantType(self):
    result = requests.post(BASE_URL + '/oauth/token', auth=('myuss.com', 'uss'))
    self.assertEqual(400, result.status_code)

  def testNormalUsage(self):
    result = requests.post(BASE_URL + '/oauth/token',
                           {'grant_type': 'client_credentials',
                            'aud': 'receiver.com'},
                           auth=('myuss.com', 'uss'))
    self.assertEqual(200, result.status_code, result.content)
    jresult = json.loads(result.content)
    access_token = jresult['access_token']

    result = requests.get(BASE_URL + '/key')
    self.assertEqual(200, result.status_code)
    public_key = result.content

    r = jwt.decode(access_token, public_key, algorithms='RS256', audience='receiver.com')
    self.assertEqual('myuss.com', r['client_id'])
    now_timestamp = int(
      (datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds())
    self.assertGreater(r['exp'], now_timestamp)
    self.assertSetEqual(set(r['scope'].split(' ')),
                        {'interuss.org_operators.read',
                         'interuss.org_operators.write'})

    time.sleep(3)
    self.assertRaises(jwt.ExpiredSignatureError,
                      lambda: jwt.decode(
                          access_token, public_key, algorithms='RS256'))


if __name__ == '__main__':
  unittest.main()
