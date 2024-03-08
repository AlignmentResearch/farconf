# FARConf: specify configurations for ML workloads

## Usage

Specify your configuration as a dataclass. Then, parse your CLI with the `parse_cli` function.

``` python
import dataclasses
from farconf import parse_cli

@dataclasses.dataclass
class Optimizer:
  name: str
  lr: float

@dataclasses.dataclass
class Algorithm:
  optimizer: Optimizer
  n_steps: int


alg: Algorithm = parse_cli(["n_steps=2", '--set-json=optimizer={"name": "adam", "lr": 0.1}'], Algorithm)
assert alg == Algorithm(Optimizer("adam", 0.1), 2)
```

### Detailed usage
Values can be fetched from YAML and Python files, and specified in the command line. Arguments are applied from left to
right onto the same `dict` object, and then parsed with `farconf.from_dict`.

  1. `--set=path.to.key=VALUE` just sets attributes `path`, `to` and `key` (for nested subclasses) to the JSON-parsed
     value `VALUE`.
      - If parsing the value as JSON fails, and the value does not contain any of the characters `{}[]"`, then it will
        be passed as a string.
      - Equivalently you can use `path.to.key=VALUE` as an argument
  2. `--set-json=path.to.key="JSON_VALUE"`. Same as above but if JSON parsing fails, parsing the command line errors.
  3. `--from-file=/path/to/file.yaml`. Incorporate the values specified in `file.yaml` into the main dict.
  3. `--set-from-file=path.to.key=PATH_TO_YAML_FILE`. Same as above, but for a sub-path.
  4. `--from-py-fn=package.module:function_name`. Points to a Python file which defines function `function_name` which,
     when called with empty arguments, will return a dataclass or dict which can be merged into the main dict.
     - The intended way is to return typed config objects with this
  4. `--set-from-py-fn=path.to.key=package.module:function_name`. Same as above but sets `path.to.key` in the main dict.



### Abstract classes
Sometimes you have different fields for different types of objects, e.g. optimizers. FARConf supports this by using
dataclasses which inherit from `abc.ABC`.

``` python
import dataclasses
from farconf import parse_cli, from_dict
import abc

@dataclasses.dataclass
class LRSchedule(abc.ABC):
  lr: float

@dataclasses.dataclass
class FlatLRSchedule(LRSchedule):
  pass

@dataclasses.dataclass
class ExpDecayLRSchedule(LRSchedule):
  discount: float = 0.999
  
  
assert from_dict(dict(_type_="__main__:FlatLRSchedule", lr=0.2), LRSchedule) == FlatLRSchedule(0.2)

assert parse_cli(["_type_=__main__:ExpDecayLRSchedule", "lr=0.2"], abc.ABC) == ExpDecayLRSchedule(0.2, discount=0.999)
```

## Goals
- Support typechecked dataclass-configurations
- Support modular, inheritance-based configurations. For example, you want to specify an optimizer, but not *which* optimizer, and different optimizers have different attributes
- Make it easy to specify hyperparameter searches
- Ingest arguments from Python files, YAML and JSON files, YAML and JSON from the command line.
- Be easy to maintain

## Non-goals
- Generate help text for configuration. Usually it'll be too long and nobody will read it.
