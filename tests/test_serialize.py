import abc
import dataclasses
import subprocess
import sys
from pathlib import Path, PurePath
from typing import Annotated, Any, Literal

import pytest
from databind.core import ConversionError, ObjectMapper
from databind.core.converter import NoMatchingConverter

from farconf import from_dict, to_dict
from farconf.serialize import (
    ABCConverter,
    deserialize_class_or_function,
    serialize_class_or_function,
)
from tests.integration.class_defs import GenericInheritor


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
    with pytest.raises(ConversionError):
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
        return 2  # pragma: no cover

    with pytest.raises(ValueError):
        serialize_class_or_function(f)


def test_serialize_main_error():
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from farconf.serialize import serialize_class_or_function

def f():
    return 2

serialize_class_or_function(f)
    """,
        ],
        stderr=subprocess.PIPE,
    )
    assert out.returncode == 1
    stderr = out.stderr.decode("utf-8")
    assert "ValueError: Cannot serialize object from `__main__`" in stderr


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


@pytest.mark.parametrize("cls", [AbstractDataClsWithType, DataClsWithType, AbstractClsWithType, ClsWithType])
def test_serialize_with_type_fails(cls: Any):
    obj = cls()
    with pytest.raises(TypeError, match="it has a '_type_' attribute which I would have to overwrite.$"):
        to_dict(obj)

    with pytest.raises(TypeError, match="it has a '_type_' attribute which I would have to overwrite.$"):
        from_dict({}, cls)


def test_path_roundtrip():
    p = Path("/path/to/something")
    assert to_dict(p) == str(p)
    assert from_dict(str(p), Path) == p


def test_float_fails():
    with pytest.raises(ConversionError):
        from_dict(dict(_type_=SERVER_TYPE, host="a", ports=[], parent=None), float)


def test_non_mapping_fails():
    mapper = ObjectMapper()
    mapper.module.register(ABCConverter())
    with pytest.raises(ConversionError):
        mapper.deserialize("hi", Path)


def test_no_class_hint_fails():
    mapper = ObjectMapper()
    mapper.module.register(ABCConverter())
    with pytest.raises(NoMatchingConverter):
        mapper.serialize("hi", Literal["hi"])

    with pytest.raises(NoMatchingConverter):
        mapper.serialize("hi", str)


def test_tmpdir_fixture_serialize(tmpdir):
    serialized = to_dict(tmpdir)
    assert serialized == str(tmpdir) and isinstance(serialized, str)

    roundtrip_tmpdir = from_dict(serialized, type(tmpdir))
    assert roundtrip_tmpdir == tmpdir

    assert to_dict(tmpdir, Path) == str(tmpdir)
    assert to_dict(tmpdir, PurePath) == str(tmpdir)

    assert from_dict(str(tmpdir), Path) == tmpdir
    assert type(from_dict(str(tmpdir), Path)) != type(tmpdir)

    assert from_dict(str(tmpdir), PurePath) == tmpdir
    assert type(from_dict(str(tmpdir), PurePath)) != type(tmpdir)


def test_serializing_does_not_miss_field():
    b = GenericInheritor(2, 3)
    out = to_dict(b, GenericInheritor)
    assert out == {"_type_": "tests.integration.class_defs:GenericInheritor", "a_field": 2, "b_field": 3}
