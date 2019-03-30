"""Manages a set of USS operations.

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

import logging


EARTH_CIRCUMFERENCE = 40.075e6  # meters
ACCURACY_VERTICAL = 0.2  # meters

log = logging.getLogger('Operations')


class ManagedOperation(object):
  def __init__(self, operation):
    self.operation = operation
    self.hidden = False


class Manager(object):
  """A repository of operations by GUFI."""

  def __init__(self):
    self._operations = {}

  def upsert_operation(self, operation):
    self._operations[operation['gufi']] = ManagedOperation(operation)

  def remove_operation(self, gufi):
    del self._operations[gufi]

  def get_managed_operation(self, gufi):
    return self._operations[gufi]

  def get_managed_operations(self):
    return self._operations.values()

  def get_operation(self, gufi):
    return self.get_managed_operation(gufi).operation

  def get_operations(self, include_hidden=False):
    return [op.operation for op in self.get_managed_operations()
            if include_hidden or not op.hidden]
