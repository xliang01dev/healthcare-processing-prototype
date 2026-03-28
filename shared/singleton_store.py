from typing import TypeVar

T = TypeVar("T")

_store: dict[type, object] = {}


def register_singleton(service_cls: type[T], instance: T) -> None:
    if instance is None:
        raise ValueError(f"Cannot register None as a singleton for {service_cls.__name__}")
    if service_cls not in _store:
        _store[service_cls] = instance


def get_singleton(service_cls: type[T]) -> T:
    instance = _store.get(service_cls)
    if instance is None:
        raise RuntimeError(
            f"No singleton registered for {service_cls.__name__} — "
            "call register_singleton before the app starts serving requests"
        )
    return instance  # type: ignore[return-value]


def remove_singleton(service_cls: type) -> None:
    if service_cls in _store:
        del _store[service_cls]
