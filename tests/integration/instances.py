from tests.integration.class_defs import (
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
