from typing import Dict, List, Set, Optional
import uuid

import s2sphere

from app.scd import geo
from app.scd.operations import Operation
from app.scd.storage import ScdStorage
from app.scd.subscriptions import Subscription


class _CellContents(object):
  subscription_ids: Set[uuid.UUID]
  operation_ids: Set[uuid.UUID]

  def __init__(self):
    self.subscription_ids = set()
    self.operation_ids = set()

  def is_empty(self) -> bool:
    return not (bool(self.subscription_ids) or bool(self.operation_ids))


class MemoryScdStorage(ScdStorage):
  subscriptions: Dict[uuid.UUID, Subscription]
  operations: Dict[uuid.UUID, Operation]
  cells: Dict[s2sphere.CellId, _CellContents]

  def __init__(self):
    self.subscriptions = {}
    self.operations = {}
    self.cells = {}

  # === Subscriptions ===
  def _remove_subscription_from_cells(self, subscription: Subscription):
    to_remove: List[s2sphere.CellId] = []
    for cell in subscription.vol4.cells:
      self.cells[cell].subscription_ids.remove(subscription.id)
      if self.cells[cell].is_empty():
        to_remove.append(cell)
    for cell in to_remove:
      del self.cells[cell]

  def get_subscription(self, id: uuid.UUID) -> Optional[Subscription]:
    return self.subscriptions.get(id, None)

  def upsert_subscription(self, subscription: Subscription):
    if subscription.id in self.subscriptions:
      old_subscription = self.subscriptions[subscription.id]
      self._remove_subscription_from_cells(old_subscription)
    self.subscriptions[subscription.id] = subscription
    for cell in subscription.vol4.cells:
      if cell not in self.cells:
        self.cells[cell] = _CellContents()
      self.cells[cell].subscription_ids.add(subscription.id)

  def find_subscriptions(self, vol4: geo.Volume4, owner: Optional[str] = None) -> List[Subscription]:
    sub_ids = set()
    for cell in vol4.cells:
      if cell in self.cells:
        sub_ids = set.union(sub_ids, self.cells[cell].subscription_ids)

    filtered = []
    for sub_id in sub_ids:
      sub = self.subscriptions[sub_id]
      if (owner is None or sub.owner == owner) and geo.overlaps_time_altitude(vol4, sub.vol4):
        filtered.append(sub)

    return filtered

  def delete_subscription(self, id: uuid.UUID):
    subscription = self.subscriptions.pop(id)
    self._remove_subscription_from_cells(subscription)

  # === Operations ===
  def _remove_operation_from_cells(self, operation: Operation):
    to_remove: List[s2sphere.CellId] = []
    for cell in operation.vol4.cells:
      self.cells[cell].operation_ids.remove(operation.id)
      if self.cells[cell].is_empty():
        to_remove.append(cell)
    for cell in to_remove:
      del self.cells[cell]

  def get_operation(self, id: uuid.UUID) -> Optional[Operation]:
    return self.operations.get(id, None)

  def upsert_operation(self, operation: Operation):
    if operation.id in self.operations:
      old_operation = self.operations[operation.id]
      self._remove_operation_from_cells(old_operation)
    self.operations[operation.id] = operation
    for cell in operation.vol4.cells:
      if cell not in self.cells:
        self.cells[cell] = _CellContents()
      self.cells[cell].operation_ids.add(operation.id)

  def find_operations(self, vol4: geo.Volume4) -> List[Operation]:
    op_ids = set()
    for cell in vol4.cells:
      if cell in self.cells:
        op_ids = set.union(op_ids, self.cells[cell].operation_ids)

    filtered = []
    for op_id in op_ids:
      op = self.operations[op_id]
      if geo.overlaps_time_altitude(vol4, op.vol4):
        filtered.append(op)

    return filtered

  def delete_operation(self, id: uuid.UUID):
    operation = self.operations.pop(id)
    self._remove_operation_from_cells(operation)

ScdStorage.register(MemoryScdStorage)
