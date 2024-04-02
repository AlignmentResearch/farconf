import abc
import json
from pathlib import Path

import pytest
import yaml
from databind.core import ConversionError
from databind.json import JsonType

from farconf import CLIParseError, parse_cli, parse_cli_into_dict
from farconf.cli import update_fns_to_cli
from tests.integration.class_defs import (
    NonAbstractDataclass,
    OneDefault,
    OneGeneric,
    OneMaybe,
    OneUnspecified,
    SubOneConfig,
    SubTwoConfig,
)
from tests.integration.instances import unspecified_two


def test_set():
    out = parse_cli_into_dict(["--set=a.b=2", "--set=b.c=3", "--set=a.b.c=4"])
    assert out == dict(b=dict(c=3), a=dict(b=dict(c=4)))


def test_raw_set():
    assert parse_cli_into_dict(["a=2"]) == dict(a=2)
    assert parse_cli_into_dict(["b.c=2", "_type_=sometype:Blah", 'a="b=c=d"']) == dict(
        b=dict(c=2), _type_="sometype:Blah", a="b=c=d"
    )


@pytest.mark.parametrize("obj", [2, "hi", [2, 5, 4], {"a": 2, "b": [{"a": 3}]}])
def test_set_json(obj: JsonType):
    assert parse_cli_into_dict([f"--set-json=a={json.dumps(obj)}"]) == {"a": obj}


INTEGRATION_DIR = Path("tests/integration")

NON_ABSTRACT_PATH = INTEGRATION_DIR / "non_abstract.yaml"
NON_ABSTRACT_ALONE_PATH = INTEGRATION_DIR / "non_abstract_alone.yaml"
ONE_PATH = INTEGRATION_DIR / "one.yaml"
ONEMAYBE_NO_PATH = INTEGRATION_DIR / "onemaybe_no.yaml"
SUBONE_PATH = INTEGRATION_DIR / "subone.yaml"
SUBTWO_PATH = INTEGRATION_DIR / "subtwo.yaml"

INSTANCES_PYPATH = "tests.integration.instances"
CLASSDEFS_PYPATH = "tests.integration.class_defs"


def test_none_abstract_parsing():
    assert parse_cli([f"--from-file={NON_ABSTRACT_PATH}"], NonAbstractDataclass) == NonAbstractDataclass(5489)
    assert parse_cli([f"--from-file={NON_ABSTRACT_ALONE_PATH}"], NonAbstractDataclass) == NonAbstractDataclass(333)

    with pytest.raises(ConversionError):
        _ = parse_cli([f"--from-file={NON_ABSTRACT_PATH}"], abc.ABC)

    with pytest.raises(KeyError, match='has no key "_type_"'):
        _ = parse_cli([f"--from-file={NON_ABSTRACT_ALONE_PATH}"], abc.ABC)


def test_yaml_cli_usage():
    assert parse_cli([f"--from-py-fn={INSTANCES_PYPATH}:maybe_yes"], OneGeneric) == OneMaybe(SubOneConfig(55555))
    assert parse_cli([f"--from-file={ONEMAYBE_NO_PATH}"], OneGeneric) == OneMaybe(None)
    assert parse_cli([f"--from-py-fn={INSTANCES_PYPATH}:default_two"], OneGeneric) == OneDefault(SubTwoConfig(1234))

    assert parse_cli([f"--from-file={ONE_PATH}"], OneGeneric) == OneDefault(SubTwoConfig(432))

    assert parse_cli([f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two"], OneGeneric) == OneUnspecified(SubTwoConfig(54321))

    assert parse_cli(
        [f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two", f"--set-from-file=c={SUBONE_PATH}"], OneGeneric
    ) == OneUnspecified(SubOneConfig(42))

    assert parse_cli(
        [f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two", f"--set-from-file=c={SUBTWO_PATH}"],
        OneGeneric,
    ) == OneUnspecified(SubTwoConfig(11))


def test_from_cli_py_only_first():
    with pytest.raises(CLIParseError, match="^--from-file= argument can only.*$"):
        parse_cli_into_dict(["--set=a=2", "--from-file=whatever"])

    with pytest.raises(CLIParseError, match="^--from-py-fn= argument can only.*$"):
        parse_cli_into_dict(["--set=a=2", "--from-py-fn=whatever"])

    with pytest.raises(CLIParseError, match="^--from-py-fn= argument can only.*$"):
        parse_cli_into_dict([f"--from-file={ONEMAYBE_NO_PATH}", "--from-py-fn=whatever"])


def test_overwrite_with_object():
    assert parse_cli(
        [
            f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two",
            f"--set-from-file=c={SUBONE_PATH}",
            f"--set-from-file=c={SUBTWO_PATH}",
        ],
        OneGeneric,
    ) == OneUnspecified(SubTwoConfig(11))

    assert parse_cli(
        [
            f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two",
            f"--set-from-file=c={SUBTWO_PATH}",
            f"--set-from-file=c={SUBONE_PATH}",
        ],
        OneGeneric,
    ) == OneUnspecified(SubOneConfig(42))


def _integration_args_and_expected() -> list[tuple[list[str], dict]]:
    with NON_ABSTRACT_PATH.open() as f:
        non_abstract_dict = yaml.load(f, yaml.SafeLoader)

    return [
        (["--set", "c.d.f.g=2"], dict(c=dict(d=dict(f=dict(g=2))))),
        (["--set-from-file", f"c.d={NON_ABSTRACT_PATH}"], dict(c=dict(d=non_abstract_dict))),
        (["--set-from-py-fn", f"e={INSTANCES_PYPATH}:maybe_no"], dict(e=dict(_type_=f"{CLASSDEFS_PYPATH}:OneMaybe", c=None))),
        (["--from-file", f"{NON_ABSTRACT_PATH}"], non_abstract_dict),
        (
            ["--from-py-fn", f"{INSTANCES_PYPATH}:default_two"],
            dict(_type_=f"{CLASSDEFS_PYPATH}:OneDefault", c=dict(_type_=f"{CLASSDEFS_PYPATH}:SubTwoConfig", two=1234)),
        ),
    ]


@pytest.mark.parametrize("args, expected", _integration_args_and_expected())
def test_quasi_well_formed_args(args: list[str], expected: dict):
    """Check that `args` with an = sign in them would be well-formed, but with a space in between are not
    well-formed."""
    assert parse_cli_into_dict(["=".join(args)]) == expected
    with pytest.raises(CLIParseError):
        parse_cli_into_dict(args)


def test_malformed_args():
    with pytest.raises(CLIParseError):
        _ = parse_cli_into_dict(["-set", "a.b=2"])

    with pytest.raises(CLIParseError):
        _ = parse_cli_into_dict(["-set=a.b=2"])

    with pytest.raises(CLIParseError):
        _ = parse_cli_into_dict(["a"])

    with pytest.raises(CLIParseError):
        _ = parse_cli_into_dict(["-a.b=2"])

    # Not really a use case we want to support, as `a-` is not a valid attribute name. But we'll allow it for now.
    assert parse_cli_into_dict(["a-._b=3"]) == {"a-": {"_b": 3}}


def test_update_fns_to_cli():
    def up1(obj: OneUnspecified) -> OneUnspecified:
        assert isinstance(obj.c, SubTwoConfig), "obj.c is the wrong type"
        obj.c.two = 3
        return obj

    def up2(obj: OneUnspecified) -> OneUnspecified:
        obj.c = SubOneConfig(234)
        return obj

    obj0 = unspecified_two()
    cli, updated_obj = update_fns_to_cli(unspecified_two)
    assert cli == ["--from-py-fn=tests.integration.instances:unspecified_two"]
    assert parse_cli(cli, OneGeneric) == obj0
    assert updated_obj == obj0

    obj1 = up1(unspecified_two())
    cli, updated_obj = update_fns_to_cli(unspecified_two, up1)
    assert cli == ["--from-py-fn=tests.integration.instances:unspecified_two", "c.two=3"]
    assert parse_cli(cli, OneGeneric) == obj1
    assert updated_obj == obj1

    obj2 = up2(up1(unspecified_two()))
    cli, updated_obj = update_fns_to_cli(unspecified_two, up1, up2)
    assert cli == [
        "--from-py-fn=tests.integration.instances:unspecified_two",
        "c.two=3",
        'c={"_type_": "tests.integration.class_defs:SubOneConfig", "one": 234}',
    ]
    assert parse_cli(cli, OneGeneric) == obj2
    assert updated_obj == obj2

    with pytest.raises(AssertionError, match="obj.c is the wrong type"):
        update_fns_to_cli(unspecified_two, up2, up1)
