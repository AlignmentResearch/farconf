import abc
import dataclasses
from typing import Annotated, Any

import pytest

from farconf import from_dict, to_dict
from farconf.serialize import deserialize_class_or_function, serialize_class_or_function


# We pepper these classes with Annotated[...] to test the `_unwrap_annotated` function
@dataclasses.dataclass
class Server:
    host: Annotated[str, "domain"] = "example.com"
    ports: list[int] = dataclasses.field(default_factory=lambda: [1337, 8888])
    parent: "Annotated[Server, 'hi'] | None" = None


@dataclasses.dataclass
class AbstractServer(abc.ABC):
    host: str = "example.com"
    ports: Annotated[list[int], "something"] = dataclasses.field(default_factory=lambda: [1337, 8888])
    parent: "Annotated[AbstractServer | None, 'whole union']" = None


SERVER_TYPE = "tests.test_serialize:Server"
ABSTRACTSERVER_TYPE = "tests.test_serialize:AbstractServer"


def SERVERS_AND_SERIALIZED() -> list[tuple[Server, dict]]:
    return [
        (Server("a", [2, 3], None), dict(host="a", ports=[2, 3], parent=None)),
        (
            Server("a", [2, 3], Server("b", [5], None)),
            dict(host="a", ports=[2, 3], parent=dict(host="b", ports=[5], parent=None)),
        ),
    ]


def ABSTRACTSERVERS_AND_SERIALIZED() -> list[tuple[AbstractServer, dict]]:
    return [
        (AbstractServer("a", [2, 3], None), dict(_type_=ABSTRACTSERVER_TYPE, host="a", ports=[2, 3], parent=None)),
        (
            AbstractServer("a", [2, 3], AbstractServer("b", [5], None)),
            dict(
                _type_=ABSTRACTSERVER_TYPE,
                host="a",
                ports=[2, 3],
                parent=dict(_type_=ABSTRACTSERVER_TYPE, host="b", ports=[5], parent=None),
            ),
        ),
    ]


@pytest.mark.parametrize("server, serialized", SERVERS_AND_SERIALIZED())
def test_serialize(server: Server, serialized: dict):
    assert to_dict(server) == serialized


@pytest.mark.parametrize("server, serialized", SERVERS_AND_SERIALIZED())
def test_deserialize(server: Server, serialized: dict):
    assert from_dict(serialized, Server) == server


@pytest.mark.parametrize("server, serialized", ABSTRACTSERVERS_AND_SERIALIZED())
def test_abc_serialize(server: AbstractServer, serialized: dict):
    assert to_dict(server) == serialized


@pytest.mark.parametrize("server, serialized", ABSTRACTSERVERS_AND_SERIALIZED())
def test_abc_deserialize(server: AbstractServer, serialized: dict):
    assert from_dict(serialized, abc.ABC) == server


@pytest.mark.parametrize("server, serialized", SERVERS_AND_SERIALIZED())
def test_abc_missing__type_(server: dict, serialized: dict):
    with pytest.raises(KeyError, match='has no key "_type_"'):
        from_dict(serialized, AbstractServer)


@pytest.mark.parametrize("server, serialized", SERVERS_AND_SERIALIZED())
def test_abc_deserialize_wrong_subtype(server: dict, serialized: dict):
    serialized["_type_"] = SERVER_TYPE
    with pytest.raises(TypeError, match="<class 'tests.test_serialize.Server'> is not a subclass of <class 'abc.ABC'>"):
        from_dict(serialized, abc.ABC)


def test_serialize_class_or_function():
    assert serialize_class_or_function(Server) == SERVER_TYPE
    assert serialize_class_or_function(AbstractServer) == ABSTRACTSERVER_TYPE
    assert serialize_class_or_function(from_dict) == "farconf.serialize:from_dict"


def test_roundtrip_class_or_function():
    for cls_or_fn in [Server, AbstractServer, from_dict, serialize_class_or_function]:
        assert deserialize_class_or_function(serialize_class_or_function(cls_or_fn)) == cls_or_fn


def test_serialize_locals_lambda_errors():
    with pytest.raises(ValueError):
        serialize_class_or_function(lambda: 2)

    def f():
        return 2

    with pytest.raises(ValueError):
        serialize_class_or_function(f)


class AbstractClsWithType(abc.ABC):
    _type_: str = "hi"


class ClsWithType:
    _type_: str = "hi"


@dataclasses.dataclass
class AbstractDataClsWithType(abc.ABC):
    _type_: str = "hi"


@dataclasses.dataclass
class DataClsWithType:
    _type_: str = "hi"


@pytest.mark.parametrize("cls", [AbstractClsWithType, ClsWithType, AbstractDataClsWithType, DataClsWithType])
def test_serialize_with_type_fails(cls: Any):
    obj = cls()
    with pytest.raises(TypeError, match="it has a '_type_' attribute which I would have to overwrite.$"):
        to_dict(obj)
