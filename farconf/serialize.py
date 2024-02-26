import abc
import importlib
from typing import Any, Callable, ClassVar, Mapping, TypeVar

import databind.json
from databind.core import Context, Converter, ObjectMapper, Setting, SettingsProvider
from databind.json.converters import SchemaConverter
from typeapi import AnnotatedTypeHint, ClassTypeHint, TypeHint


def _unwrap_annotated(hint: TypeHint) -> TypeHint:
    if isinstance(hint, AnnotatedTypeHint):
        return hint[0]
    return hint


def serialize_class_or_function(cls_or_fn: type | Callable) -> str:
    """Converts class or function into a "module:qualname" string."""
    out = f"{cls_or_fn.__module__}:{cls_or_fn.__qualname__}"
    if "<locals>" in out or "<lambda>" in out:
        raise ValueError(f"Cannot serialize object {cls_or_fn} because it is ephemeral.")
    return out


def deserialize_class_or_function(value: str) -> type | Callable:
    """Imports some class or function from a "module:qualname" string."""
    module_name, qualname = value.split(":")
    module = importlib.import_module(module_name)

    obj: Any = module
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


class ABCConverter(Converter):
    """Serializes and deserializes abstract base classes (abc.ABC) by storing their concrete type."""

    _TYPE_KEY: ClassVar[str] = "_type_"

    def convert(self, ctx: Context) -> Any:
        datatype = _unwrap_annotated(ctx.datatype)
        if not isinstance(datatype, ClassTypeHint):
            raise NotImplementedError

        if hasattr(datatype.type, "_type_"):
            raise TypeError(
                f"Trying to de/serialize an object of class {datatype.type}, but it has a '{self._TYPE_KEY}' attribute which I would "
                "have to overwrite."
            )

        if ctx.direction.is_serialize():
            if not issubclass(datatype.type, abc.ABC):
                raise NotImplementedError

            cls = ctx.value.__class__
            ctx.datatype = TypeHint(cls)
            out = SchemaConverter().convert(ctx)
            assert self._TYPE_KEY not in out
            out[self._TYPE_KEY] = serialize_class_or_function(cls)
            return out

        elif ctx.direction.is_deserialize():
            cls: type[abc.ABC] = datatype.type

            if not (isinstance(ctx.value, Mapping) and self._TYPE_KEY in ctx.value):
                if issubclass(cls, abc.ABC):
                    raise KeyError(
                        f'Input {ctx.value} has no key "{self._TYPE_KEY}", so I don\'t know which subclass of {cls} to instantiate.'
                    )
                raise NotImplementedError

            ctx.value = dict(ctx.value)  # Copy before popping
            cls_path: str = ctx.value.pop(self._TYPE_KEY)
            concrete_cls: type[abc.ABC] = deserialize_class_or_function(cls_path)  # type: ignore
            ctx.datatype = TypeHint(concrete_cls)
            if not issubclass(concrete_cls, cls):
                raise TypeError(
                    f"_type_-specified class {concrete_cls} is not a subclass of {cls}, which was specified via Python "
                    "type hints."
                )
            out = SchemaConverter().convert(ctx)
            return out
        else:
            raise ValueError(f"Unknown {ctx.direction=}")  # pragma: no cover


def get_object_mapper() -> ObjectMapper[Any, databind.json.JsonType]:
    mapper = databind.json.get_object_mapper()
    mapper.module.register(ABCConverter(), first=True)
    return mapper


T = TypeVar("T")


def from_dict(
    value: databind.json.JsonType, datatype: type[T], *, settings: SettingsProvider | list[Setting] | None = None
) -> T:
    "Get a value of type `datatype` from a dict object."
    return get_object_mapper().deserialize(value, datatype, settings=settings)


def to_dict(
    value: Any, datatype: type[T] | None = None, *, settings: SettingsProvider | list[Setting] | None = None
) -> databind.json.JsonType:
    "Convert `value` to a dict object which can be serialized."
    if datatype is None:
        datatype = type(value)
    return get_object_mapper().serialize(value, datatype, settings=settings)
