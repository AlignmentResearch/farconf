import abc
from pathlib import Path
from typing import Sequence

import pytest
import yaml

from farconf import CLIParseError, parse_cli, parse_cli_into_dict
from tests.integration.class_defs import (
    NonAbstractDataclass,
    OneDefault,
    OneGeneric,
    OneUnspecified,
    SubTwoConfig,
)
from tests.integration.instances import OneMaybe, SubOneConfig


def test_set():
    out = parse_cli_into_dict(["--set=a.b=2", "--set=b.c=3", "--set=a.b.c=4"])
    assert out == dict(b=dict(c=3), a=dict(b=dict(c=4)))


def test_raw_set():
    assert parse_cli_into_dict(["a=2"]) == dict(a=2)
    assert parse_cli_into_dict(["b.c=2", "_type_=sometype:Blah", "a=b=c=d"]) == dict(
        b=dict(c=2), _type_="sometype:Blah", a="b=c=d"
    )


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

    with pytest.raises(TypeError):
        _ = parse_cli([f"--from-file={NON_ABSTRACT_PATH}"], abc.ABC, type_check_partial=False)

    with pytest.raises(CLIParseError):
        _ = parse_cli([f"--from-file={NON_ABSTRACT_PATH}"], abc.ABC, type_check_partial=True)

    with pytest.raises(KeyError, match='has no key "_type_"'):
        _ = parse_cli([f"--from-file={NON_ABSTRACT_ALONE_PATH}"], abc.ABC, type_check_partial=False)


def test_yaml_cli_usage():
    assert parse_cli([f"--from-py-fn={INSTANCES_PYPATH}:maybe_yes"], OneGeneric) == OneMaybe(SubOneConfig(55555))
    assert parse_cli(
        [f"--from-py-fn={INSTANCES_PYPATH}:maybe_yes", f"--from-file={ONEMAYBE_NO_PATH}"], OneGeneric
    ) == OneMaybe(None)
    assert parse_cli([f"--from-py-fn={INSTANCES_PYPATH}:default_two"], OneGeneric) == OneDefault(SubTwoConfig(1234))

    assert parse_cli([f"--from-py-fn={INSTANCES_PYPATH}:default_two", f"--from-file={ONE_PATH}"], OneGeneric) == OneDefault(
        SubTwoConfig(432)
    )

    assert parse_cli([f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two"], OneGeneric) == OneUnspecified(SubTwoConfig(54321))

    assert parse_cli(
        [f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two", f"--set-from-file=c={SUBONE_PATH}"], OneGeneric
    ) == OneUnspecified(SubOneConfig(42))

    assert parse_cli(
        [f"--from-py-fn={INSTANCES_PYPATH}:unspecified_two", f"--set-from-file=c={SUBTWO_PATH}"],
        OneGeneric,
    ) == OneUnspecified(SubTwoConfig(11))


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
def test_quasi_well_formed_args(args: Sequence[str], expected: dict):
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
