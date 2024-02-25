from tests.integration.class_defs import (
    OneDefault,
    OneMaybe,
    OneUnspecified,
    SubOneConfig,
    SubTwoConfig,
)

unspecified_two = OneUnspecified(SubTwoConfig(53421))
default_two = OneDefault(SubTwoConfig(1234))
maybe_yes = OneMaybe(SubOneConfig(55555))
maybe_no = OneMaybe(None)
