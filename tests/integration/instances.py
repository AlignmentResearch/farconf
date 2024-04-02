from tests.integration.class_defs import (
    ClassWithList,
    OneDefault,
    OneMaybe,
    OneUnspecified,
    SubOneConfig,
    SubTwoConfig,
)


def unspecified_two():
    return OneUnspecified(SubTwoConfig(54321))


def default_two():
    return OneDefault(SubTwoConfig(1234))


def maybe_yes():
    return OneMaybe(SubOneConfig(55555))


def maybe_no():
    return OneMaybe(None)


def class_with_list():
    return ClassWithList(a=[2, 3, 4, 5])
