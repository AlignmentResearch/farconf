from pathlib import Path
from typing import Sequence

import pytest
import yaml

from farconf import CLIParseError, parse_cli_into_dict


def test_set():
    out = parse_cli_into_dict(["--set=a.b=2", "--set=b.c=3", "--set=a.b.c=4"])
    assert out == dict(b=dict(c=3), a=dict(b=dict(c=4)))


INTEGRATION_DIR = Path("tests/integration")

NON_ABSTRACT_PATH = INTEGRATION_DIR / "non_abstract.yaml"
INSTANCES_PYPATH = "tests.integration.instances"
CLASSDEFS_PYPATH = "tests.integration.class_defs"


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
