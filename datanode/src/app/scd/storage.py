from abc import ABC, abstractmethod
from typing import List, Optional
import uuid

from app.scd import geo

from app.scd.subscriptions import Subscription

class ScdStorage(ABC):
  @abstractmethod
  def get_subscription(self, id: uuid.UUID) -> Optional[Subscription]:
    pass

  @abstractmethod
  def upsert_subscription(self, subscription: Subscription):
    pass

  @abstractmethod
  def find_subscriptions(self, vol4: geo.Volume4, owner: str) -> List[Subscription]:
    pass

  @abstractmethod
  def delete_subscription(self, id: uuid.UUID) -> Optional[Subscription]:
    pass
