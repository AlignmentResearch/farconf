"""Parse and create command-line arguments
"""
import dataclasses
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence, TypeVar

import yaml
from databind.json import JsonType

from farconf.config_ops import Atom, config_diff, config_merge
from farconf.serialize import deserialize_class_or_function, from_dict, serialize_class_or_function, to_dict

T = TypeVar("T")


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


JSON_LIKE_CHARS = r'\[\]{}"'
INTENDED_JSON = re.compile(f"^.*[{JSON_LIKE_CHARS}].*$")


def assign_from_keyvalue(out: dict[str, Any], key_value_pair: str) -> None:
    path_to_key, value = _equals_key_and_value(key_value_pair)
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError as e:
        if INTENDED_JSON.fullmatch(value):
            raise json.JSONDecodeError(msg=f"From CLI assignment {repr(key_value_pair)}: {e.msg}", doc=e.doc, pos=e.pos)
        else:
            parsed_value = value

    assign_from_dotlist(out, path_to_key, parsed_value)


class CLIParseError(ValueError):
    pass


def parse_cli_into_dict(args: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arg_idx, arg in enumerate(args):
        if arg.startswith("--set="):
            _, key_value_pair = _equals_key_and_value(arg)
            assign_from_keyvalue(out, key_value_pair)

        elif arg.startswith("--set-json="):
            _, key_value_pair = _equals_key_and_value(arg)
            path_to_key, value = _equals_key_and_value(key_value_pair)
            parsed_value = json.loads(value)
            assign_from_dotlist(out, path_to_key, parsed_value)

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
            if arg_idx != 0:
                raise CLIParseError(f"--from-file= argument can only be the first argument, but I received {args}")

            _, file_path = _equals_key_and_value(arg)
            with Path(file_path).open() as f:
                d = yaml.load(f, yaml.SafeLoader)
            assert isinstance(d, dict), "Unsupported non-dict files"
            assert out == {}
            out = d

        elif arg.startswith("--from-py-fn="):
            if arg_idx != 0:
                raise CLIParseError(f"--from-py-fn= argument can only be the first argument, but I received {args}")
            _, module_path = _equals_key_and_value(arg)
            fn = deserialize_class_or_function(module_path)

            d = to_dict(fn())
            assert isinstance(d, dict), "Unsupported non-dict objects"
            assert out == {}
            out = d

        else:
            if arg.startswith("-"):
                raise CLIParseError(
                    "Only `--set`, `--set-json`, `--set-from-file`, `--from-file`,  `--from-py-fn` and "
                    "`--set-from-py-fn` arguments can start with `-`. If you need to set a key which starts with `-`, "
                    "use `--set=-key-name=value`."
                )
            if "=" not in arg:
                raise CLIParseError(f"Argument {arg} is not a valid assignment, it contains no `=`.")
            assign_from_keyvalue(out, arg)

    return out


def parse_cli(args: list[str], datatype: type[T]) -> T:
    cfg: dict = parse_cli_into_dict(args)
    out = from_dict(cfg, datatype)
    return out


def _obj_as_dot_updates(obj: Atom | JsonType) -> list[tuple[list[str], str]]:
    # If one of the keys has a `.` in it, we can't set it in the command line directly -- that will be incorrect.
    if isinstance(obj, Mapping) and not any(("." in k) for k in obj.keys()):
        out: list[tuple[list[str], str]] = []
        for k, value in obj.items():
            repr_values = _obj_as_dot_updates(value)
            out.extend(([k] + ls, v) for (ls, v) in repr_values)
        return out
    else:
        if isinstance(obj, Atom):
            obj = obj.obj
        return [([], json.dumps(obj))]


def obj_to_cli(obj: Atom | JsonType) -> list[str]:
    updates = _obj_as_dot_updates(obj)
    return [f"{'.'.join(keys)}={value}" for keys, value in updates]


def _sequence_is_leaf_if_different(c_from: Any, c_to: Any) -> bool:
    """
    Setting individual objects on the CLI does not support merging lists. Thus,
    we consider lists/tuples as leaves always.

    NOTE: if CLI-serializing just lists were permitted, we also would need to check that (c_from != c_to). Otherwise,
    the diff for two identical lists is `c_to`. This case does not arise when using `update_fns_to_cli`, but we test for
    it anyways in `tests/test_cli.py::test_update_list_nothing`
    """
    return isinstance(c_to, Sequence) and (c_from != c_to)


if TYPE_CHECKING:
    from _typeshed import DataclassInstance  # pragma: no cover

    DataclassT = TypeVar("DataclassT", bound=DataclassInstance)  # pragma: no cover
else:
    DataclassT = T


def update_fns_to_cli(
    fn_obj: Callable[[], DataclassT], *updates: Callable[[DataclassT], DataclassT]
) -> tuple[list[str], DataclassT]:
    """
    Returns command-line which will generate the updates from *updates.
    """
    prev_dict_obj = fn_obj()
    cur_obj = fn_obj()

    # We have to ensure these are two different objects because the `updates` may mutate their input
    if cur_obj is prev_dict_obj:
        raise ValueError(f"{fn_obj=} should create an entirely new object every time it is called.")

    cli: list[str] = [f"--from-py-fn={serialize_class_or_function(fn_obj)}"]

    prev_dict = to_dict(prev_dict_obj)
    for update in updates:
        cur_obj = update(cur_obj)

        cur_dict = to_dict(cur_obj)
        diff = config_diff(prev_dict, cur_dict, is_leaf=_sequence_is_leaf_if_different)
        new_prev_dict = config_merge(prev_dict, diff)
        assert new_prev_dict == cur_dict
        prev_dict = new_prev_dict

        cli.extend(obj_to_cli(diff))

        assert parse_cli_into_dict(cli) == cur_dict

    return cli, cur_obj


def typed_dotlist(obj: DataclassT, *, _prefix: str = "") -> DataclassT:
    """Create dotlists in a typed way."""
    Cls = obj.__class__

    # Create a new dotlist generator class, which is an instance of the same classes `obj` is an instance of. This lets
    # us assert that attributes are of particular classes, which lets us do typechecking and completion in the IDE.
    class _DotlistGenerator(Cls):  # type: ignore
        _obj: Any
        _prefix: str

        def __init__(self, _obj: Any, _prefix: str) -> None:
            self._obj = _obj
            self._prefix = _prefix

        def __getattribute__(self, name: str, /) -> Any:
            new_obj = getattr(object.__getattribute__(self, "_obj"), name)
            if name.startswith("__") and name.endswith("__"):
                # Just return dunder attributes of the _obj
                return new_obj

            # Add this attribute's name to the prefix
            prefix = object.__getattribute__(self, "_prefix")
            new_prefix = name if prefix == "" else f"{prefix}.{name}"

            # Before creating another typed_dotlist, check whether the new object is still a dataclass.  If it is not,
            # it is pointless to keep track of the prefix anyways, because we shouldn't need to take any more
            # attributes.
            #
            # Besides, `new_obj` might be something like an int: an object which is hard to subclass
            if not dataclasses.is_dataclass(new_obj):
                return new_prefix

            assert not isinstance(new_obj, type)
            return typed_dotlist(new_obj, _prefix=new_prefix)

        def __str__(self) -> str:
            return object.__getattribute__(self, "_prefix")

    return _DotlistGenerator(obj, _prefix)  # type: ignore
