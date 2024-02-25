from pathlib import Path
from typing import Any, Mapping, Sequence, TypeVar

import yaml

from farconf.serialize import deserialize_class_or_function, from_dict, to_dict

T = TypeVar("T")


def merge_two_mappings(d1: Mapping[str, Any], d2: Mapping[str, Any]) -> dict[str, Any]:
    """Merge two Mappings. Merging occurs by assigning the keys in `d2` and their recursive children onto the same
    leaves of `d1`; unless the dicts of `d2` are wrapped in a `Leaf` object.
    """
    out = dict(d1)  # Shallow copy and convert to dict
    for key, value in d2.items():
        if isinstance(value, Mapping) and key in out and isinstance(out_at_key := out[key], Mapping):
            out[key] = merge_two_mappings(out_at_key, value)
        else:
            out[key] = value
    return out


def _equals_key_and_value(s: str) -> tuple[str, str]:
    key, *value = s.split("=")
    return key, "=".join(value)


def assign_from_dotlist(out: dict[str, Any], dot_key: str, value: Any) -> None:
    non_recursive_keys = dot_key.split(".")

    x = out
    for key in non_recursive_keys[:-1]:
        if key not in x or not isinstance(x[key], dict):
            # If there's already some non-dict assigned here, or there's nothing, create a new dict.
            x[key] = dict()
        x = x[key]

    x[non_recursive_keys[-1]] = value


def assign_from_keyvalue(out: dict[str, Any], key_value_pair: str) -> None:
    path_to_key, value = _equals_key_and_value(key_value_pair)
    parsed_value = yaml.load(value, yaml.SafeLoader)

    assign_from_dotlist(out, path_to_key, parsed_value)


class CLIParseError(ValueError):
    pass


def parse_cli_into_dict(args: Sequence[str], *, datatype: type | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arg in args:
        if arg.startswith("--set="):
            _, key_value_pair = _equals_key_and_value(arg)
            assign_from_keyvalue(out, key_value_pair)

        elif arg.startswith("--set-from-file="):
            _, key_value_pair = _equals_key_and_value(arg)

            path_to_key, file_path = _equals_key_and_value(key_value_pair)
            with Path(file_path).open() as f:
                parsed_value = yaml.load(f, yaml.SafeLoader)
            assign_from_dotlist(out, path_to_key, parsed_value)

        elif arg.startswith("--set-from-py-fn="):
            _, key_value_pair = _equals_key_and_value(arg)

            path_to_key, module_path = _equals_key_and_value(key_value_pair)
            fn = deserialize_class_or_function(module_path)
            serialized_object = to_dict(fn())
            assign_from_dotlist(out, path_to_key, serialized_object)

        elif arg.startswith("--from-file="):
            _, file_path = _equals_key_and_value(arg)
            with Path(file_path).open() as f:
                d = yaml.load(f, yaml.SafeLoader)
            out = merge_two_mappings(out, d)

        elif arg.startswith("--from-py-fn="):
            _, module_path = _equals_key_and_value(arg)
            fn = deserialize_class_or_function(module_path)

            d = to_dict(fn())
            out = merge_two_mappings(out, d)

        else:
            if arg.startswith("-"):
                raise CLIParseError(
                    "Only `--set`, `--set-from-file`, `--from-file`,  `--from-py-fn` and `--set-from-py-fn` arguments "
                    "can start with `-`. If you need to set a key which starts with `-`, use `--set=-key-name=value`."
                )
            if "=" not in arg:
                raise CLIParseError(f"Argument {arg} is not a valid assignment, it contains no `=`.")
            assign_from_keyvalue(out, arg)

        if datatype is not None:
            try:
                _ = from_dict(out, datatype)
            except Exception as e:
                raise CLIParseError(
                    f"Failed to parse command-line input after argument {arg}. Full CLI: {args}. Original exception: {e}"
                )

    return out


def parse_cli(args: Sequence[str], datatype: type[T]) -> T:
    cfg: dict = parse_cli_into_dict(args)
    out = from_dict(cfg, datatype)
    return out
