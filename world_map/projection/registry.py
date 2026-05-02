from __future__ import annotations

from typing import Callable

from world_map.projection.base import MapProjectionConfig

_REGISTRY: dict[str, Callable[..., MapProjectionConfig]] = {}


def register(key: str):
    """Decorator: @register('utm')"""
    def decorator(factory: Callable[..., MapProjectionConfig]):
        _REGISTRY[key] = factory
        return factory
    return decorator


def build(key: str, **kwargs) -> MapProjectionConfig:
    if key not in _REGISTRY:
        valid = ', '.join(sorted(_REGISTRY))
        raise KeyError(f"Unknown projection '{key}'. Valid: {valid}")
    return _REGISTRY[key](**kwargs)
