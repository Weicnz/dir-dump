from __future__ import annotations

from typing import Any

from .base import DirectoryStrategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, DirectoryStrategy] = {}

    def register(self, strategy: DirectoryStrategy) -> None:
        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> DirectoryStrategy | None:
        return self._strategies.get(name)

    def all(self) -> list[DirectoryStrategy]:
        return list(self._strategies.values())

    def names(self) -> list[str]:
        return list(self._strategies.keys())


def get_registry() -> StrategyRegistry:
    from .current_dir_strategy import CurrentDirStrategy

    registry = StrategyRegistry()
    registry.register(CurrentDirStrategy())
    return registry
