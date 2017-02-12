# coding=utf-8

from abc import abstractmethod, abstractproperty

from .decorators import TypedProperty
from .singleton import Singleton


class ProgressAdapter:
    @abstractproperty
    def name(self) -> str:
        """"""

    @abstractmethod
    def start(self, title: str, length: int = 100, label: str = ''):
        """"""

    @abstractmethod
    def set_value(self, value: int):
        """"""

    @abstractmethod
    def set_label(self, value: str):
        """"""

    @abstractmethod
    def done(self):
        """"""


class Progress(metaclass=Singleton):
    def __init__(self, adapters: list = None):
        if adapters is None:
            adapters = []
        else:
            for adapter in adapters:
                self._check_adapter(adapter)
        self._adapters = adapters
        self._title = None
        self._label = None
        self._value = 0
        self._length = 100
        self._is_started = False

    @staticmethod
    def _check_adapter(adapter):
        if not isinstance(adapter, ProgressAdapter):
            raise TypeError(type(adapter))

    def has_adapter(self, adapter: str or ProgressAdapter = None):
        if isinstance(adapter, ProgressAdapter):
            adapter = adapter.name
        for adapter_ in self._adapters:
            if adapter_.name == adapter:
                return True

    def register_adapter(self, adapter: ProgressAdapter):
        self._check_adapter(adapter)
        if self.has_adapter(adapter):
            raise RuntimeError('adapter already registered: {}'.format(adapter.name))
        self._adapters.append(adapter)

    def unregister_adapter(self, adapter: ProgressAdapter or str):
        if isinstance(adapter, ProgressAdapter):
            adapter = adapter.name
        if self.has_adapter(adapter):
            for adapter_ in self._adapters:
                if adapter_.name == adapter:
                    self._adapters.remove(adapter_)
                    return True

    @property
    def is_started(self):
        return self._is_started

    @TypedProperty(int)
    def value(self, value: int) -> int:
        if value > self.length:
            raise ValueError(value)
        if value == self.length:
            self.done()
        return value

    @TypedProperty(str)
    def title(self, value: str) -> str:
        return value

    @TypedProperty(str)
    def label(self, value: str) -> str:
        return value

    @TypedProperty(int)
    def length(self, value: int) -> int:
        if value <= 0:
            raise ValueError('expected a positive integer, got: {}'.format(value))
        return value

    def start(self, title: str, length: int = 100, label: str = '', start_index: int = 0):
        if self.is_started:
            raise RuntimeError('progress already running')
        for adapter in self._adapters:
            assert isinstance(adapter, ProgressAdapter)
            adapter.start(title, length, label)
        self.length = length
        self.title = title
        self.label = label
        self.value = start_index
        self._is_started = True

    def done(self):
        for adapter in self._adapters:
            assert isinstance(adapter, ProgressAdapter)
            adapter.done()
        self._is_started = False
