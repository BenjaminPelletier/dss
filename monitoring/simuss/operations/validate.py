import datetime
from typing import Any, Callable, Dict, List, Optional
import uuid

import pytimeparse


Validator = Callable[[Any, str], List[str]]
FieldValidator = Callable[[Dict, str, str], List[str]]


def field(validator: Validator, required: bool=True) -> FieldValidator:
  def validate_field(parent: Dict, field_name: str, source: str) -> List[str]:
    if field_name in parent:
      return validator(parent[field_name], '{}.{}'.format(source, field_name))
    elif required:
      return ['Missing `{}` in `{}`'.format(field_name, source)]
    else:
      return []
  return validate_field


def defined_dict(fields: Dict[str, FieldValidator], chained_validator: Optional[Validator]=None) -> Validator:
  def validate_dict(v: Any, source: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(v, dict):
      errors.append('Expected dict in `{}`'.format(source))
    else:
      if chained_validator is not None:
        errors.extend(chained_validator(v, source))
      for field_name, field_validator in fields.items():
        errors.extend(field_validator(v, field_name, source))
    return errors
  return validate_dict


def list_of(validator: Validator, min_items: Optional[int]=None, max_items: Optional[int]=None) -> Validator:
  def validate_list(v: Any, source: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(v, list):
      errors.append('Expected list in `{}`'.format(source))
    else:
      if min_items is not None:
        if len(v) < min_items:
          errors.append('Expected at least {} elements in `{}` but found {}'.format(min_items, source, len(v)))
      if max_items is not None:
        if len(v) > max_items:
          errors.append('Expected no more than {} elements in `{}` but found {}'.format(max_items, source, len(v)))
      for i, item in enumerate(v):
        errors.extend(validator(item, '{}[{}]'.format(source, i)))
    return errors
  return validate_list


def one_field_of(*field_names: str) -> Validator:
  field_list = ', '.join('`{}`'.format(field_name) for field_name in field_names)
  def validate_one_field(v: Any, source: str) -> List[str]:
    n_found = sum(1 if field_name in field_names else 0 for field_name in v)
    if n_found > 1:
      return ['Only one of {} may be specified in `{}`'.format(field_list, source)]
    elif n_found == 0:
      return ['One of {} must be specified in `{}`'.format(field_list, source)]
    else:
      return []
  return validate_one_field


def validate_all(*validators: Validator) -> Validator:
  def validate(v: Any, source: str):
    errors: List[str] = []
    for validator in validators:
      errors.extend(validator(v, source))
    return errors
  return validate


def constant_value(expected_value: str) -> Validator:
  def validate_constant(v: Any, source: str) -> List[str]:
    if not isinstance(v, str):
      return ['Expected string in `{}`'.format(source)]
    if v != expected_value:
        return ['Expected `{}`="{}", found "{}"'.format(source, expected_value, v)]
    return []
  return validate_constant


def time_value(value: Any, source: str) -> List[str]:
  errors: List[str] = []
  if not isinstance(value, str):
    errors.append('Expected string in `{}`'.format(source))
  else:
    try:
      datetime.datetime.fromisoformat(value)
    except ValueError as e:
      errors.append('Unable to parse `{}`: {}'.format(source, str(e)))
  return errors


def timedelta_value(value: Any, source: str) -> List[str]:
  errors: List[str] = []
  if not isinstance(value, str):
    errors.append('Expected string in `{}`'.format(source))
  else:
    try:
      pytimeparse.timeparse.timeparse(value)
    except ValueError as e:
      errors.append('Unable to parse `{}`="{}": {}'.format(source, value, e))
  return errors


def numeric_value(min_value: Optional[float]=None, max_value: Optional[float]=None) -> Validator:
  def validate_numeric_field(v: Any, source: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(v, float) and not isinstance(v, int):
      errors.append('Expected numeric value in `{}`'.format(source))
    else:
      if min_value is not None:
        if v < min_value:
          errors.append('Value {} for `{}` is below minimum of {}'.format(v, source, min_value))
      if max_value is not None:
        if v > max_value:
          errors.append('Value {} for `{}` is above maximum of {}'.format(v, source, max_value))
    return errors
  return validate_numeric_field


def enum_value(values: List[str]) -> Validator:
  def validate_enum(v: Any, source: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(v, str):
      errors.append('Expected string in `{}`'.format(source))
    else:
      if v not in values:
        errors.append('Value "{}" in `{}` is not in the allowed set of \{{}\}'.format(v, source, ', '.join(values)))
    return errors
  return validate_enum


def uuid_value(v: Any, source: str) -> List[str]:
  errors: List[str] = []
  if not isinstance(v, str):
    errors.append('Expected string in `{}`'.format(source))
  else:
    try:
      uuid.UUID(v)
    except ValueError as e:
      errors.append('Could not parse "{}" in `{}` as UUID: {}'.format(v, source, str(e)))
  return errors


def boolean_value(v: Any, source: str) -> List[str]:
  errors: List[str] = []
  if not isinstance(v, bool):
    errors.append('Expected boolean in `{}`'.format(source))
  return errors


scd_time = defined_dict({
  'format': field(constant_value('RFC3339')),
  'value': field(time_value),
})


simuss_timedelta = defined_dict({
  'format': field(constant_value('TimeDelta')),
  'value': field(timedelta_value),
})


scd_altitude = defined_dict({
  'reference': field(constant_value('W84')),
  'units': field(constant_value('M')),
  'value': field(numeric_value()),
})


lat_lng_point = defined_dict({
  'lat': field(numeric_value(-90, 90)),
  'lng': field(numeric_value(-180, 180)),
})


scd_radius = defined_dict({
  'value': field(numeric_value(0)),
  'units': field(constant_value('M')),
})


scd_outline_circle = defined_dict({
  'center': field(lat_lng_point),
  'radius': field(scd_radius),
})


scd_outline_polygon = defined_dict({
  'vertices': field(list_of(lat_lng_point, 3)),
})


scd_volume3d = defined_dict({
  'altitude_lower': field(scd_altitude),
  'altitude_upper': field(scd_altitude),
  'outline_circle': field(scd_outline_circle, required=False),
  'outline_polygon': field(scd_outline_polygon, required=False),
}, chained_validator=one_field_of('outline_circle', 'outline_polygon'))


def scd_volume4d(allow_relative_time: bool=False) -> Validator:
  if allow_relative_time:
    return defined_dict({
      'time_start': field(scd_time, required=False),
      'time_end': field(scd_time, required=False),
      'timedelta_start': field(simuss_timedelta, required=False),
      'timedelta_end': field(simuss_timedelta, required=False),
      'volume': field(scd_volume3d),
    }, chained_validator=validate_all(
      one_field_of('time_start', 'timedelta_start'),
      one_field_of('time_end', 'timedelta_end'),
    ))
  else:
    return defined_dict({
      'time_start': field(scd_time),
      'time_end': field(scd_time),
      'volume': field(scd_volume3d),
    })


scd_operation_descriptor = defined_dict({
  'extents': field(list_of(scd_volume4d(allow_relative_time=True))),
  'state': field(enum_value(["Accepted", "Activated", "NonConforming", "Contingent", "Ended"])),
  'notify_for_constraints': field(boolean_value),
  'vlos': field(boolean_value),
})
