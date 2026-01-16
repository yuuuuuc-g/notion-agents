from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IVectorStore(ABC):
    """
    向量存储的抽象接口 (Repository Interface)
    定义了业务层必须调用的标准方法
    """

    @abstractmethod
    def add_memory(
        self,
        page_id: str,
        text: str,
        *,
        title: str = None,
        domain: str = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        pass

    @abstractmethod
    def search_memory(
        self,
        query_text: str,
        n_results: int = 3,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        pass
