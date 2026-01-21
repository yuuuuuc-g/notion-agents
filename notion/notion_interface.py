from abc import ABC, abstractmethod
from typing import Dict, List


class INotionService(ABC):
    """Notion 服务抽象接口"""

    @abstractmethod
    def create_page(self, title: str, children: List[Dict], icon: str = "🧠") -> Dict:
        pass

    @abstractmethod
    def delete_page(self, page_id: str) -> bool:
        pass
