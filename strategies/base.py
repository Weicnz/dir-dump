from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DirectoryItem:
    name: str
    path: str
    category: str = "other"
    icon: str | None = None
    color: str | None = None


class DirectoryStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        ...

    @abstractmethod
    def get_recommendations(
        self, current_dir: str | None, config: dict[str, Any]
    ) -> list[DirectoryItem]:
        ...
