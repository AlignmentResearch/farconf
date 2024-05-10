import abc
import dataclasses
from typing import Generic, TypeVar


class BaseConfig(abc.ABC):
    pass


@dataclasses.dataclass
class SubOneConfig(BaseConfig):
    one: int


@dataclasses.dataclass
class SubTwoConfig(BaseConfig):
    two: int


class OneGeneric(abc.ABC):
    pass


@dataclasses.dataclass
class OneUnspecified(OneGeneric):
    c: BaseConfig


@dataclasses.dataclass
class OneDefault(OneGeneric):
    c: BaseConfig = dataclasses.field(default_factory=lambda: SubOneConfig(2))


@dataclasses.dataclass
class OneMaybe(OneGeneric):
    c: BaseConfig | None = None


@dataclasses.dataclass
class NonAbstractDataclass:
    a: int


@dataclasses.dataclass
class ClassWithList:
    a: list[int]


T = TypeVar("T")


@dataclasses.dataclass
class GenericClass(Generic[T], abc.ABC):
    a_field: int


@dataclasses.dataclass
class GenericInheritor(GenericClass):
    b_field: int
