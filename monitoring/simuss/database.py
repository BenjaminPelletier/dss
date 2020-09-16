import datetime
import glob
import os
from typing import Dict, List, Optional

import yaml


class Database(object):
  TABLE_OPERATIONS = 'operations'
  TABLE_OPERATION_NOTIFICATIONS = 'operation_notifications'

  def __init__(self, db_path: str):
    self.db_path = db_path

  def _table_path(self, table: str):
    table_path = os.path.join(self.db_path, table)
    os.makedirs(table_path, exist_ok=True)
    return table_path

  def make_id(self, table: str, code: str):
    n = len(os.listdir(self._table_path(table)))
    return '{:06d}_{}_{}.yaml'.format(
      n, datetime.datetime.now().strftime('%H%M%S_%f'), code)

  def get_filename(self, table: str, id: str):
    return os.path.join(table, '{}.yaml'.format(id))

  def put(self, table: str, id: str, content: Dict) -> None:
    fullname = os.path.join(self._table_path(table), '{}.yaml'.format(id))
    with open(fullname, 'w') as f:
      f.write(yaml.dump(content, indent=2))

  def list_ids(self, table: str) -> List[str]:
    return [os.path.splitext(filename)[0]
            for filename
            in glob.glob(os.path.join(self._table_path(table), '*.yaml'))]

  def get(self, table: str, id: str) -> Optional[Dict]:
    filename = os.path.join(self._table_path(table), '{}.yaml'.format(id))
    try:
      with open(filename, 'r') as f:
        return yaml.load(f)
    except ValueError:
      return None
