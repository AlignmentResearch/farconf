import dataclasses
from pathlib import Path
from typing import Any, Mapping, Sequence, TypeVar

import yaml

from farconf.serialize import from_dict

T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class Leaf:
    "Tag an object as being an in-separable leaf, for `merge_mappings`."

    obj: Any


def merge_two_mappings(d1: Mapping[str, Any], d2: Mapping[str, Leaf | Any]) -> dict[str, Any]:
    """Merge two Mappings. Merging occurs by assigning the keys in `d2` and their recursive children onto the same
    leaves of `d1`; unless the dicts of `d2` are wrapped in a `Leaf` object.
    """
    out = dict(d1)  # Shallow copy and convert to dict
    for key, value in d2.items():
        if isinstance(value, Mapping) and key in out:
            out[key] = merge_two_mappings(out[key], value)
        elif isinstance(value, Leaf):
            out[key] = value.obj
        else:
            out[key] = value
    return out


def _equals_key_and_value(s: str) -> tuple[str, str]:
    key, *value = s.split("=")
    return key, "=".join(value)


def dict_from_dotlist(dot_key: str, value: Any) -> dict[str, Any]:
    non_recursive_keys = dot_key.split(".")

    out: dict[str, Any] = {non_recursive_keys[-1]: value}
    for k in reversed(non_recursive_keys[:-1]):
        out = {k: out}
    return out


def dict_from_keyvalue(key_value_pair: str) -> dict[str, Any]:
    path_to_key, value = _equals_key_and_value(key_value_pair)
    parsed_value = yaml.load(value, yaml.SafeLoader)
    d = dict_from_dotlist(path_to_key, Leaf(parsed_value))
    return d


def parse_cli_into_dict(args: Sequence[str], *, datatype: type | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arg in args:
        if arg.startswith("--set="):
            _, key_value_pair = _equals_key_and_value(arg)
            d = dict_from_keyvalue(key_value_pair)

        elif arg.startswith("--set-from-file="):
            _, key_value_pair = _equals_key_and_value(arg)

            path_to_key, file_path = _equals_key_and_value(key_value_pair)
            with Path(file_path).open() as f:
                parsed_value = yaml.load(f, yaml.SafeLoader)
            d = dict_from_dotlist(path_to_key, Leaf(parsed_value))

        elif arg.startswith("--from-file="):
            _, file_path = _equals_key_and_value(arg)
            with Path(file_path).open() as f:
                d = yaml.load(f, yaml.SafeLoader)

        else:
            if arg.startswith("-"):
                raise ValueError(
                    "Only `--set`, `--set-from-file` and `--from-file` arguments can start with `-`. If you need to set a key which starts "
                    "with `-`, use `--set=-key-name=value`."
                )
            if "=" not in arg:
                raise ValueError(f"Argument {arg} is not a valid assignment, it contains no `=`.")

            d = dict_from_keyvalue(arg)
        out = merge_two_mappings(out, d)
    return out


def parse_cli(args: Sequence[str], datatype: type[T]) -> T:
    cfg: dict = parse_cli_into_dict(args)
    out = from_dict(cfg, datatype)
    return out
