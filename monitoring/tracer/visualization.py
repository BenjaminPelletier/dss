import datetime
import glob
import os
import re
from typing import Optional

import yaml

from monitoring.monitorlib.fetch.rid import FetchedISAs
from monitoring.monitorlib.fetch.scd import FetchedEntities


class UTMState(object):
  def __init__(self):
    self.isas = None
    self.operations = None
    self.constraints = None
    self.timestamp = None


class UTMError(object):
  def __init__(self, title, description):
    self.title = title
    self.description = description


log_matcher = re.compile(r'^(\d{6})_(\d{6}_\d{6})_(.*?)\.yaml$')


def read_current_state(path: str, index: Optional[int]=None) -> UTMState:
  state = UTMState()
  state.timestamp = datetime.datetime.utcnow()

  read_polled_ops = False
  read_polled_isas = False
  read_polled_constraints = False
  missing_op_details = set()
  missing_constraint_details = set()
  missing_isa_details = set()
  subscription_parameters = None
  polling_parameters = None
  errors = []

  for filename in sorted(glob.glob(os.path.join(path, '*.yaml')), reverse=True):
    match = log_matcher.match(os.path.basename(filename))
    if not match:
      continue
    f_index = int(match.group(1))
    f_timestamp = datetime.datetime.strptime(match.group(2), '%H%M%S_%f')
    f_type = match.group(3)

    if index is not None:
      if f_index > index:
        continue
      index = None
      state.timestamp = f_timestamp

    if (read_polled_ops and
        read_polled_isas and
        read_polled_constraints and
        not missing_op_details and
        not missing_isa_details and
        not missing_constraint_details and
        subscription_parameters and
        polling_parameters):
      # No more information needed
      break

    if 'poll_isas' in f_type and not read_polled_isas:
      # This file is a result of polling ISAs
      with open(filename, 'r') as f:
        isa_poll = FetchedISAs(yaml.full_load(f))
      if isa_poll.success:
        state.isas = isa_poll.isas
      else:
        errors.append(UTMError('ISA query in DSS', 'Error querying DSS for ISAs: ' + isa_poll.error))
      read_polled_isas = True

    elif 'poll_ops' in f_type and not read_polled_ops:
      # This file is a result of polling Operations
      with open(filename, 'r') as f:
        op_poll = FetchedEntities(yaml.full_load(f))
      if op_poll.success:
        state.operations = op_poll.entities_by_id
      else:
        errors.append(UTMError('Op references query in DSS', 'Error querying DSS for operation references: ' + op_poll.error))
      read_polled_ops = True

    elif 'poll_constraints' in f_type and not read_polled_constraints:
      # This file is a result of polling Constraints
      with open(filename, 'r') as f:
        constraint_poll = FetchedEntities(yaml.full_load(f))
      if constraint_poll.success:
        state.constraints = constraint_poll.entities_by_id
      else:
        errors.append(UTMError('Constraint references query in DSS', 'Error querying DSS for constraint references: ' + constraint_poll.error))
      read_polled_constraints = True

    elif 'notify_isa' in f_type and missing_isa_details:
      # This file is a result of receiving an ISA notification
      pass

    elif 'notify_op' in f_type and missing_op_details:
      # This file is a result of receiving an Operation notification
      pass

    elif 'notify_constraint' in f_type and missing_constraint_details:
      # This file is a result of receiving a Constraint notification
      pass

    elif 'subscribe_start' in f_type and not subscription_parameters:
      # This file defines the start of a Subscription session
      with open(filename, 'r') as f:
        config = yaml.full_load(f)
      coords = [float(v) for v in config['area'].split(',')]
      state.subscribe_area = {'lat_lo': min(coords[0], coords[2]),
                              'lng_lo': min(coords[1], coords[3]),
                              'lat_hi': max(coords[0], coords[2]),
                              'lng_hi': max(coords[1], coords[3])}

    elif 'poll_start' in f_type and not polling_parameters:
      # This file defines the start of a polling session
      pass

  return state
