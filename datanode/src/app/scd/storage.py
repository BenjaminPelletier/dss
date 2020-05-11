from abc import ABC, abstractmethod
from typing import List, Optional
import uuid

from app.scd import geo

from app.scd.operations import Operation
from app.scd.subscriptions import Subscription

class ScdStorage(ABC):
  # === Subscriptions ===
  @abstractmethod
  def get_subscription(self, id: uuid.UUID) -> Optional[Subscription]:
    pass

  @abstractmethod
  def upsert_subscription(self, subscription: Subscription):
    pass

  @abstractmethod
  def find_subscriptions(self, vol4: geo.Volume4, owner: Optional[str] = None) -> List[Subscription]:
    pass

  @abstractmethod
  def delete_subscription(self, id: uuid.UUID):
    pass

  # === Operations ===
  @abstractmethod
  def get_operation(self, id: uuid.UUID) -> Optional[Operation]:
    pass

  @abstractmethod
  def upsert_operation(self, operation: Operation):
    pass

  @abstractmethod
  def find_operations(self, vol4: geo.Volume4) -> List[Operation]:
    pass

  @abstractmethod
  def delete_operation(self, id: uuid.UUID):
    pass
