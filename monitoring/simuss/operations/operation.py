import copy
import datetime
import json
from typing import Dict, Optional

from pytimeparse.timeparse import timeparse
import yaml

from monitoring.simuss import webapp


def from_file(format: str, content: str) -> Dict:
  if format == 'json':
    return json.loads(content)
  elif format == 'yaml':
    return yaml.safe_load(content)
  else:
    raise ValueError('Unsupported format "{}"'.format(format))


def _replace_timedeltas(node: Dict, t0: datetime.datetime) -> Dict:
  result = {}
  for k, v in node.items():
    if isinstance(v, dict):
      if v.get('format', None) == 'TimeDelta':
        result[k.replace('timedelta', 'time')] = {
          'format': 'RFC3339',
          'value': (t0 + datetime.timedelta(seconds=timeparse(v['value']))).isoformat() + 'Z',
        }
      else:
        result[k] = _replace_timedeltas(v, t0)
    else:
      result[k] = v
  return result


def reference_request_from_descriptor(descriptor: Dict, old: Optional[Dict]=None) -> Dict:
  uss_base_url = webapp.config['USS_BASE_URL']
  req = {
    'extents': _replace_timedeltas(descriptor['extents'], datetime.datetime.utcnow()),
    'old_version': old['reference']['old_version'] if old else 0,
    'state': descriptor['state'],
    'uss_base_url': uss_base_url,
  }
  if old:
    req['subscription_id'] = old['reference']['subscription_id']
  else:
    req['new_subscription'] = {
      'uss_base_url': uss_base_url,
      'notify_for_constraints': descriptor['notify_for_constraints']
    }
  return req
