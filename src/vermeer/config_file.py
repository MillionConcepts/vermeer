
from pathlib import Path
import pyyaml as yaml
from . import steps
from .step import Step
from . import __version__, SCHEMA_DIR
from errors import ConfigError
from datetime import datetime


class PipelineConfig:
    """
    Class for the configuration of a whole run. Stores and adds to pipeline
    configurations indicated in the original config file. Supplements with
    defaults in hardware config file or
    """

    def __init__(self, config_file):

        # generate random run ID version here? time or more random than that?
        self.run_ID = datetime.now.strftime("%Y%m%dT%H%M%SZ")

        # read config file
        self.config_file = Path(config_file)
        config = read_yaml(self.config_file)
        self.config_problems = []

        # load yaml schema file
        self.schema_version = str(config.get("yaml_schema_version"))
        self.schema_path = SCHEMA_DIR / f"config_schema_{self.schema_version}.yaml"
        self.schema = read_yaml(self.schema_path)

        # checks basic config things, then set attributes from config
        config, problems = check_config_schema(config, self.schema)
        self.config_problems.extend(problems)

        for key, value in config.items():
            # this will overwrite anything previously set (e.g. schema_version)
            setattr(self, key, value)

        # check config steps against step subclasses, set default
        # Each processing step listed gets loaded
        step_list = config.get("calibration_steps")
        if not step_list:
            self.config_problems.append("calibration_steps is empty, there"
                                        "are no processing steps to run.")
        self.steps = []
        for position, step in enumerate(step_list, start=1):
            self.add_step(position, step)

        # Alert to all problems gathered
        if self.config_problems:


    def add_step(self, position, step):

        # check each step in the config has the required components. this is
        # a check against the config YAML schema, not each step subclass.
        step, problems = check_config_schema(
            step,
            self.schema["calibration_steps"]["step_requirements"]
        )
        self.config_problems.extend(problems)

        # step ID must be unique for each step in calibration pipeline
        step_id = step["id"]
        if step["id"] in [s.id for s in self.steps]:
            self.config_problems.append(f"{step_id}: id is used twice")

        # check the steps listed are steps that exist, get Step subclass of
        # the specified step
        step_class = Step.all_steps.get(step["step"])
        if step_class is None:
            self.config_problems.append(f"'{step['step']}' step unknown.")
            return

        params = self.get_params(step_class, step)
        inputs = self.get_inputs(step_class, step, position)
        outputs = self.get_outputs(step_class, step, position)
        retain = self.get_retain(step_class, step, position)

        self.steps.append(step_class(
            step_id,
            params,
            inputs,
            outputs,
            retain
        ))

    def get_params(self, step_class, step, position):
        # check step subclass params
        # use defaults if not defined by config file
        return

    def get_inputs(self, step_class, step, position):
        # check step subclass inputs
        # check if required files exist or not
        return

    def get_outputs(self, step_class, step, position):
        # check step subclass outputs
        # make output filenames with output prefix
        return

    def get_retain(self, step_class, step, position):
        # check step subclass retain rules
        # modify to all true if retain_on_failure
        # write or not write?
        return


def write_config(pipeline_config):
    # write config file in yaml format
    # from PipelineConfig class
    return


def read_yaml(yaml_path):
    if not read_yaml(yaml_path).is_file():
        raise ConfigError(f"No config file was found at: {yaml_path}")
    try:
        config = yaml.safe_load(yaml_path.read_text())
    except yaml.YAMLError as e:
        # pyyaml specific errors
        raise ConfigError(f"{yaml_path} is not valid YAML: {e}") from e
    if not isinstance(config, dict):
        raise ConfigError(f"{yaml_path} did not load as a valid dict for "
                          f"pipeline configuration.")
    return config


def check_config_schema(config, schema):
    """
    Check all values expected by YML schema are in the config file, and
    warn about unexpected values.
    """
    problems = []
    for key in config:
        if key not in schema:
            problems.append(f"'{key}' not in config schema.")
    checked = {}
    for key, rule in schema.items():
        if key in config:
            value = config[key]
        elif rule.get("required", False):
            problems.append(f"'{key}' is required")
            continue
        else:
            value = rule.get("default")
        value, error = check_config_type(value, rule["type"], key)
        if error:
            problems.append(f"'{key}': {error}")
        checked[key] = value
    return checked, problems


def check_config_type(config_value, config_type, key):
    """ Check configured value is type expected by config YML schema."""
    if type(config_value) is not config_type:
        return config_value, (f"expected {config_type}, "
                              f"got {type(config_value).__name__} for {key}")
    return config_value, None