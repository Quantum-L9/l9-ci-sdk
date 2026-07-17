"""Provider registry implementation."""

from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass, field
from .spi import Provider


@dataclass(slots=True)
class ProviderRegistry:
    """Explicit provider registry.
    Registration is deterministic and duplicate provider identifiers are
    rejected.
    """

    _providers: dict[str, Provider] = field(default_factory=dict)

    def register(self, provider: Provider) -> None:
        provider_id = provider.metadata.provider_id
        if provider_id in self._providers:
            raise ValueError(f"provider already registered: {provider_id}")
        self._providers[provider_id] = provider

    def unregister(self, provider_id: str) -> None:
        try:
            del self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"provider is not registered: {provider_id}") from exc

    def get(self, provider_id: str) -> Provider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"provider is not registered: {provider_id}") from exc

    def contains(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def providers(self) -> tuple[Provider, ...]:
        return tuple(
            self._providers[provider_id] for provider_id in self.provider_ids()
        )

    def __iter__(self) -> Iterator[Provider]:
        return iter(self.providers())

    def __len__(self) -> int:
        return len(self._providers)
