from typing import Dict, List, Set, Optional
import uuid

import s2sphere

from app.scd import geo
from app.scd.subscriptions import Subscription
from app.scd.storage import ScdStorage


class _CellContents(object):
  subscription_ids: Set[uuid.UUID]

  def __init__(self):
    self.subscription_ids = set()

  def is_empty(self) -> bool:
    return bool(self.subscription_ids)


class MemoryScdStorage(ScdStorage):
  subscriptions: Dict[uuid.UUID, Subscription]
  cells: Dict[s2sphere.CellId, _CellContents]

  def __init__(self):
    self.subscriptions = {}
    self.cells = {}

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


  def find_subscriptions(self, vol4: geo.Volume4, owner: str) -> List[Subscription]:
    sub_ids = set()
    for cell in vol4.cells:
      if cell in self.cells:
        sub_ids = sub_ids | self.cells[cell].subscription_ids

    filtered = []
    for sub_id in sub_ids:
      sub = self.subscriptions[sub_id]
      include = True
      if sub.owner != owner:
        include = False
      if include and vol4.time_start is not None and sub.vol4.time_end < vol4.time_start:
        include = False
      if include and vol4.time_end is not None and sub.vol4.time_start > vol4.time_end:
        include = False
      if include and vol4.altitude_lo is not None and sub.vol4.altitude_hi < vol4.altitude_lo:
        include = False
      if include and vol4.altitude_hi is not None and sub.vol4.altitude_lo > vol4.altitude_hi:
        include = False
      if include:
        filtered.append(sub)

    return filtered

  def delete_subscription(self, id: uuid.UUID) -> Optional[Subscription]:
    subscription = self.subscriptions.pop(id)
    if subscription is not None:
      self._remove_subscription_from_cells(subscription)
    return subscription


ScdStorage.register(MemoryScdStorage)
