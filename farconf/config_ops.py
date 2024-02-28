"""Manipulate configuration mappings
"""


from dataclasses import dataclass
from typing import Any, Callable, Generic, Mapping, Sequence, TypeVar, overload

from farconf.serialize import ABCConverter

T = TypeVar("T")


@dataclass
class Atom(Generic[T]):
    """Marks objects inside a Config as being indivisible for merging purposes.

    Attributes:
        obj: The object that should not be merged.
    """

    obj: T


LeafCallable = Callable[[Any, Any], bool]


def _never(_, __):
    return False


@overload
def config_merge(c1: Mapping[str, T], c2: Mapping[str, T], *, is_leaf: LeafCallable = _never) -> dict[str, T]:
    ...  # pragma: no cover


@overload
def config_merge(c1: Sequence[T], c2: Sequence[T], *, is_leaf: LeafCallable = _never) -> list[T]:
    ...  # pragma: no cover


@overload
def config_merge(c1: Any, c2: T | Atom[T], *, is_leaf: LeafCallable = _never) -> T:
    ...  # pragma: no cover


def config_merge(c1, c2, *, is_leaf=_never):
    """Merge two mappings or sequences.

    Merging occurs by assigning the keys in `c2` and their recursive children
    onto the same leaves of `c1`; unless the values of `c2` are wrapped in a
    `Atom` object or `is_leaf(c1, c2)` is true.

    Args:
        c1: The first mapping or sequence to merge.
        c2: The second mapping or sequence to merge.
        is_leaf: A function that returns True if the given object should
            not be merged.

    Returns:
        The merged mapping, sequence, or non-merged object.
    """

    if isinstance(c2, Atom):
        return c2.obj

    elif is_leaf(c1, c2):
        return c2

    elif isinstance(c1, Mapping):
        if isinstance(c2, Mapping):
            out = dict(c1)
            for key, value in c2.items():
                if key in out:
                    out[key] = config_merge(out[key], value, is_leaf=is_leaf)
                else:
                    out[key] = value
            return out
        else:
            return c2

    elif not isinstance(c1, str) and isinstance(c1, Sequence):
        if not isinstance(c2, str) and isinstance(c2, Sequence):
            out = [config_merge(i1, i2, is_leaf=is_leaf) for (i1, i2) in zip(c1, c2)]
            out.extend(c2[len(c1) :])
            return out
        else:
            return c2
    else:
        return c2


def _contains_different_type_key(c1: Any, c2: Any) -> bool:
    """True if both c1 and c2 are Mappings, both contain _type_ keys, and they are different."""
    _tk = ABCConverter._TYPE_KEY
    if isinstance(c1, Mapping) and isinstance(c2, Mapping) and _tk in c1 and _tk in c2:
        return c1[_tk] != c2[_tk]
    return False


@overload
def config_diff(
    c_from: Mapping[str, T], c_to: Mapping[str, T], *, is_leaf: LeafCallable = _contains_different_type_key
) -> Atom[dict[str, T]] | dict[str, T]:
    ...  # pragma: no cover


@overload
def config_diff(
    c_from: Sequence[T], c_to: Sequence[T], *, is_leaf: LeafCallable = _contains_different_type_key
) -> Atom[list[T]] | list[T]:
    ...  # pragma: no cover


@overload
def config_diff(c_from: Any, c_to: T, *, is_leaf: LeafCallable = _contains_different_type_key) -> T:
    ...  # pragma: no cover


def config_diff(c_from, c_to, *, is_leaf=_contains_different_type_key):
    """Output the minimal `update` such that `merge(c_from, update) == c_to`.

    Args:
        c_from: The original config object.
        c_to: The target config object.
        is_leaf: A function that returns True if the given object should be considered atomic and represented as an
            `Atom` regardless of whether it can be achieved by a merge. By default, all Mappings with the "_type_" key
            are represented as an Atom if the key is different.

    Returns:
        The minimal update to c_from that would result in c_to when merged.
        Returns an Atom if c_to cannot be represented as an update.

    This is always possible because of the existence of the `Atom()` class. This function prefers to use `Atom` the
    minimal amount.
    """

    if isinstance(c_to, Atom):
        return c_to

    elif isinstance(c_from, Mapping):
        if is_leaf(c_from, c_to):
            return Atom(c_to)

        if isinstance(c_to, Mapping):
            c_from_keys = set(c_from.keys())
            c_to_keys = set(c_to.keys())

            if not c_to_keys.issuperset(c_from_keys):
                return Atom(c_to)

            subtract_set = c_to_keys - c_from_keys
            # Iterate with a filter to preserve order of keys
            out = {k: c_to[k] for k in c_to_keys if k in subtract_set}

            union_set = c_from_keys & c_to_keys
            for key in c_from_keys:
                # Iterate with a `k in union_set` filter to preserve key order
                if key in union_set:
                    if (v_from := c_from[key]) != (v_to := c_to[key]):
                        out[key] = config_diff(v_from, v_to)
            return out

        else:
            return Atom(c_to)

    elif not isinstance(c_from, str) and isinstance(c_from, Sequence):
        if is_leaf(c_from, c_to):
            return Atom(c_to)

        if not isinstance(c_to, str) and isinstance(c_to, Sequence):
            if len(c_to) > len(c_from):
                return Atom(c_to)

            out = list(c_to)
            for i, from_value in enumerate(c_from):
                out[i] = config_diff(from_value, out[i])
            return out
        else:
            return Atom(c_to)

    # No need to check _is_leaf here because this will always be considered a leaf by `config_merge`.
    return c_to
