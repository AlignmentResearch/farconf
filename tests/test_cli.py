from farconf import parse_cli_into_dict
from farconf.cli import obj_to_cli


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
