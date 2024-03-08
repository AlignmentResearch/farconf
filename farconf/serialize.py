import abc
import dataclasses
import importlib
from pathlib import PurePath
from typing import Any, Callable, ClassVar, Mapping, Optional, Type, TypeVar

import databind.json
from databind.core import (
    Context,
    ConversionError,
    Converter,
    ObjectMapper,
    Setting,
    SettingsProvider,
)
from databind.json.converters import SchemaConverter, StringifyConverter
from typeapi import AnnotatedTypeHint, ClassTypeHint, TypeHint


def _unwrap_annotated(hint: TypeHint) -> TypeHint:
    if isinstance(hint, AnnotatedTypeHint):
        return hint[0]
    return hint


def serialize_class_or_function(cls_or_fn: type | Callable) -> str:
    """Converts class or function into a "module:qualname" string."""
    mod_name = cls_or_fn.__module__
    if mod_name == "__main__":
        raise ValueError(
            f"Cannot serialize object from `__main__` ({cls_or_fn}) because `__main__` may be different in a different run."
        )
    out = f"{mod_name}:{cls_or_fn.__qualname__}"
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
            # This should never raise when the ABCConverter is at the end
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
            # Copy context, replacing the datatype
            new_ctx = dataclasses.replace(ctx, datatype=TypeHint(cls))
            out = SchemaConverter().convert(new_ctx)
            # Create new dict so _TYPE_KEY goes first.
            out = {self._TYPE_KEY: serialize_class_or_function(cls), **out}
            return out

        elif ctx.direction.is_deserialize():
            cls: type[abc.ABC] = datatype.type

            if not isinstance(ctx.value, Mapping):
                raise ConversionError(self, ctx, f"value must be a Mapping to deserialize into {cls}")

            if self._TYPE_KEY not in ctx.value:
                if issubclass(cls, abc.ABC):
                    raise KeyError(
                        f'Input {ctx.value} has no key "{self._TYPE_KEY}", so I don\'t know which subclass of {cls} to instantiate.'
                    )
                raise NotImplementedError

            new_ctx_value = dict(ctx.value)  # Copy before popping
            cls_path: str = new_ctx_value.pop(self._TYPE_KEY)
            concrete_cls: type[abc.ABC] = deserialize_class_or_function(cls_path)  # type: ignore
            if not issubclass(concrete_cls, cls):
                raise ConversionError(
                    self,
                    ctx,
                    f"_type_-specified class {concrete_cls} is not a subclass of {cls}, which was specified via Python "
                    "type hints.",
                )

            new_ctx = dataclasses.replace(ctx, value=new_ctx_value, datatype=TypeHint(concrete_cls))
            out = SchemaConverter().convert(new_ctx)
            return out
        else:
            raise ValueError(f"Unknown {ctx.direction=}")  # pragma: no cover


T = TypeVar("T")


class LenientStringifyConverter(StringifyConverter):
    """De/serializes a type that can be converted to string, but does not pay as much attention to the serialization type"""

    def __init__(
        self,
        type_: Type[T],
        alt_serialize_type_: Type,
        parser: Optional[Callable[[str], T]] = None,
        formatter: Callable[[T], str] = str,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(type_, parser, formatter, name)
        self.alt_serialize_type_ = alt_serialize_type_

    def convert(self, ctx: Context) -> Any:
        if ctx.direction.is_serialize():
            datatype = _unwrap_annotated(ctx.datatype)
            # If we're serializing and the requested type is the alt_serialize_type_, patch context so it contains `self.type_` instead.
            if isinstance(datatype, ClassTypeHint) and issubclass(datatype.type, self.alt_serialize_type_):
                ctx = dataclasses.replace(ctx, datatype=TypeHint(self.type_))

        return super().convert(ctx)


def get_object_mapper() -> ObjectMapper[Any, databind.json.JsonType]:
    mapper = databind.json.get_object_mapper()
    converters = mapper.module.converters[0].converters  # type: ignore
    for i in range(len(converters)):
        if isinstance(converters[i], SchemaConverter):
            # Add the ABCConverter just before the SchemaConverter
            converters.insert(i, ABCConverter())

    try:
        import _pytest._py.path

        # Using the tmpdir fixture in pytest (https://docs.pytest.org/en/6.2.x/tmpdir.html) yields this LocalPath type. Make it transparent to Path
        mapper.module.register(
            LenientStringifyConverter(
                _pytest._py.path.LocalPath, alt_serialize_type_=PurePath, name="_pytest._py.path:LocalPath"
            )
        )
    except ImportError:  # pragma: no cover
        pass  # pragma: no cover

    assert any(isinstance(c, ABCConverter) for c in converters)
    return mapper


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
