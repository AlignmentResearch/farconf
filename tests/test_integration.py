from farconf import parse_cli_into_dict


def test_set():
    out = parse_cli_into_dict(["--set=a.b=2", "--set=b.c=3", "--set=a.b.c=4"])
    assert out == dict(b=dict(c=3), a=dict(b=dict(c=4)))
