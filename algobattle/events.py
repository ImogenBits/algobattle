"""basic event handling module."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import ClassVar, Generic, Mapping, TypeVar, Union

from algobattle.util import Table


T = TypeVar("T")


class Observer(ABC, Generic[T]):
    """Class that can handle updates from a `Subject`."""

    @abstractmethod
    def update(self, event: str, data: T) -> None:
        """Updates the observer with the provided data."""
        raise NotImplementedError


class Subject(ABC, Generic[T]):
    """Class that can send updates to an `Observer`."""

    default_event: ClassVar[str]
    """Event used when none is specififed for `.notify()`."""

    observers: list[Observer[T]]
    """List of observers currently attached to this."""

    def __init__(self) -> None:
        super().__init__()
        self.observers = []

    def notify(self, data: T, event: str | None = None) -> None:
        """Notifies all attached observers."""
        if event is None:
            event = self.default_event
        for observer in self.observers:
            observer.update(event, data)

    def attach(self, observer: Observer[T]) -> None:
        """Attaches the observer, making it receive any future updates."""
        if observer not in self.observers:
            self.observers.append(observer)

    def detach(self, observer: Observer[T]) -> None:
        """Detaches the observer, making it not receive any future updates."""
        try:
            self.observers.remove(observer)
        except ValueError:
            pass


UiData = Union[Table, Mapping, str, None]


class _UiDispatcher(Observer[UiData], Subject[UiData]):
    """Singleton class that handles the shared subject/observer objects."""

    default_event = "systeminfo"
    observers: list[UiObserver]

    def update(self, event: str, data: UiData) -> None:
        self.notify(data, event)

    def cleanup(self) -> None:
        for observer in self.observers:
            observer.cleanup()
        self.observers = []


ui_dispatcher = _UiDispatcher()


class UiObserver(Observer[UiData], ABC):
    """An `Observer` that will receive updates from any `UiSubject`."""

    def __init__(self) -> None:
        super().__init__()
        ui_dispatcher.attach(self)

    def cleanup(self) -> None:
        """Cleans up the ui state."""
        pass


class UiSubject(Subject[UiData], ABC):
    """A `Subject` that will update all `UiObserver`s."""

    def __init__(self) -> None:
        super().__init__()
        self.attach(ui_dispatcher)
