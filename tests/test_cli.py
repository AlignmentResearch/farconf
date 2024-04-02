import json

import pytest

from farconf import obj_to_cli, parse_cli, parse_cli_into_dict, update_fns_to_cli
from farconf.serialize import serialize_class_or_function
from tests.integration.class_defs import ClassWithList, OneDefault, SubOneConfig
from tests.integration.instances import class_with_list


def test_obj_to_cli():
    obj = {
        "a": "baba",
        "b": {"_type_": "some:Class"},
        "c": None,
        "d": {"e": True, "f": False},
        "g": 1e-8,
        "h": 1.2e-8,
        "i": 1.24,
        "j": 0xFF,
        "k": [{"hi": "bye"}, 2, "no"],
    }
    expected_output = [
        'a="baba"',
        'b._type_="some:Class"',
        "c=null",
        "d.e=true",
        "d.f=false",
        "g=1e-08",
        "h=1.2e-08",
        "i=1.24",
        "j=255",
        'k=[{"hi": "bye"}, 2, "no"]',
    ]
    assert obj_to_cli(obj) == expected_output
    assert parse_cli_into_dict(expected_output) == obj


def test_cli_set_invalid_json():
    for s in '[]{}"':
        if s in "[]":
            regex_s = "\\" + s
        else:
            regex_s = s
        with pytest.raises(json.JSONDecodeError, match=f"From CLI assignment 'a={regex_s}'"):
            parse_cli_into_dict([f"a={s}"])

        with pytest.raises(json.JSONDecodeError):
            parse_cli_into_dict([f"--set=a={s}"])

        with pytest.raises(json.JSONDecodeError):
            parse_cli_into_dict([f"--set-json=a={s}"])

    for s in ["fsda b", "' '", "() ()", "b: 2"]:
        assert parse_cli_into_dict([f"a={s}"]) == dict(a=s)
        assert parse_cli_into_dict([f"--set=a={s}"]) == dict(a=s)

        with pytest.raises(json.JSONDecodeError):
            parse_cli_into_dict([f"--set-json=a={s}"])


def test_update_fns_same_obj():
    def update_fn(od: OneDefault) -> OneDefault:
        od.c = SubOneConfig(1234)
        return od

    _, cur_obj = update_fns_to_cli(OneDefault, update_fn)
    assert cur_obj == update_fn(OneDefault())

    _onedefault_closure_obj = OneDefault()

    def onedefault_closure():
        return _onedefault_closure_obj

    with pytest.raises(ValueError, match=f"{onedefault_closure} should create an entirely new object"):
        update_fns_to_cli(onedefault_closure)

    with pytest.raises(ValueError, match="Cannot serialize object <.*> because it is ephemeral"):
        update_fns_to_cli(lambda: OneDefault())


def test_update_list_partial():
    def update_fn(obj: ClassWithList) -> ClassWithList:
        obj.a[0] = 5
        obj.a[1] = 2
        return obj

    parsed_obj = parse_cli([f"--from-py-fn={serialize_class_or_function(class_with_list)}", "a=[5, 2]"], ClassWithList)
    assert parsed_obj == update_fn(class_with_list())

    _, cur_obj = update_fns_to_cli(class_with_list, update_fn)
    assert cur_obj == update_fn(class_with_list())
