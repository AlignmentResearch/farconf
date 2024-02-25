# FARConf: specify configurations for ML workloads

## Goals
- Support typechecked dataclass-configurations
- Support modular, inheritance-based configurations. For example, you want to specify an optimizer, but not *which* optimizer, and different optimizers have different attributes
- Make it easy to specify hyperparameter searches
- Ingest arguments from Python files, YAML and JSON files, YAML and JSON from the command line.
- Be easy to maintain

## Non-goals
- Generate help text for configuration. Usually it'll be too long and nobody will read it.
