import copy
import datetime
import json
from typing import Dict, List, Optional

from pytimeparse.timeparse import timeparse
import yaml
from yaml.representer import Representer

import monitoring.monitorlib.mutate.scd


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


class Details(dict):
  pass
yaml.add_representer(Details, Representer.represent_dict)


class Descriptor(dict):
  @classmethod
  def from_file(cls, format: str, content: str):
    if format == 'json':
      return Descriptor(json.loads(content))
    elif format == 'yaml':
      return Descriptor(yaml.safe_load(content))
    else:
      raise ValueError('Unsupported format "{}"'.format(format))

  @property
  def valid(self) -> bool:
    if not self.get('extents'):
      return False
    if not self.get('type'):
      return False
    return True

  def get_extents(self, t0: datetime.datetime) -> List[Dict]:
    return [_replace_timedeltas(v, t0) for v in copy.deepcopy(self['extents'])]

  @property
  def type(self) -> str:
    return self['type']

  def to_details(self, t0: datetime.datetime) -> Details:
    return Details({
      'volumes': self.get_extents(t0),
      'type': self.type,
    })
yaml.add_representer(Descriptor, Representer.represent_dict)


class Owned(dict):
  @classmethod
  def from_mutation(cls, dss: monitoring.monitorlib.mutate.scd.MutatedEntity, details: Details):
    result = Owned()
    result['dss'] = dss
    result['uss'] = {'details': details}
    return result

  @property
  def dss(self) -> monitoring.monitorlib.mutate.scd.MutatedEntity:
    return self['dss']
yaml.add_representer(Owned, Representer.represent_dict)
