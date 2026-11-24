
from pathlib import Path
import yaml
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
        step_list = config.get("calibration_steps") or []
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
        if 'id' not in step.keys():
            step_id = step["step"]
        else:
            step_id = step["id"]
        if step["id"] in [s.id for s in self.steps]:
            self.config_problems.append(f"{step_id}: id is used twice")

        # check the steps listed are steps that exist, get Step subclass of
        # the specified step
        step_class = Step.all_steps.get(step["step"])
        if step_class is None:
            self.config_problems.append(f"'{step['step']}' step unknown.")
            return

        params = self.get_params(
                step_class,
                step['params'],
                step_id
            )
        inputs = self.get_inputs(step_class, step['inputs'], step_id)

        #TODO: I like this way of loading inputs and outputs but in terms of
        # outputs, the output paths, what needs to be saved/written, kept
        # in memory, etc. between steps, maybe outputs / retain should
        # be contained in an output class? or as part of the DataModel class?
        # so for every input / output we create a DataModel class that
        # we call to read / write according to their params in the orchestrator
        # loop?
        # in which case, PipelineConfig is massive....
        # so I think it's better to keep all data in run specific dict when
        # running happens and the corresponding keys are tracked via
        # PipelineConfig products, which contains all expected input and output
        # info, including when to write, keep in memory, etc each one.
        # and that will be used to modify the run specific dict of images/data
        # during the pipeline loop
        # so products of pipelineconfig will be like a card catalog for
        # checking data in / out, return by date etc
        outputs = self.get_outputs(step_class, step['outputs'], step_id)
        retain = self.get_retain(step_class, step['retain'], step_id)

        self.steps.append(step_class(
            step_id,
            params,
            inputs,
            outputs,
            retain
        ))

    def get_inputs(
            self,
            step_class,
            config_inputs,
            step_id
    ):
        """
        Check inputs in config against step class definitions, use defaults
        if required parameters are not filled in. I think most input files
        would be required.
        """
        cleaned_inputs = {}

        for key in config_inputs:
            if key not in step_class.inputs:
                self.config_problems.append(f"Unknown input '{key}' in "
                                            f"{step_id}")
        for key in step_class.inputs:
            if key in config_inputs:
                cleaned_inputs[key] = config_inputs[key]
            # add an elif for checking the hardware config file (which hasn't
            # been loaded yet / doesn't have a given format)
            else:
                self.config_problems.append(f"{step_id}: Input '{key}' is "
                                            f"required")
        return cleaned_inputs


    def get_outputs(
            self,
            step_class,
            config_inputs,
            step_id
    ):
        """
        Check outputs in config against step class definitions, use defaults
        if required parameters are not filled in.

        Output files may or may not be written, they also may or may not be
        kept in memory.
        """
        #TODO: add info on output writing / retaining here? or separate
        # loader? or should we scrap this way of loading and make outputs
        # part of the. see above to do.
        cleaned_ouputs = {}

        for key in config_inputs:
            if key not in step_class.inputs:
                self.config_problems.append(f"Unknown input '{key}' in "
                                            f"{step_id}")
        for key in step_class.inputs:
            if key in config_inputs:
                cleaned_ouputs[key] = config_inputs[key]
            else:
                # make default output path here?
                cleaned_ouputs[key] = make_out_path(step_id, key)
        return cleaned_ouputs


    def get_retain(self, step_class, step, step_id):
        # check step subclass retain rules
        # modify to all true if retain_on_failure
        # write or not write?
        return


    def get_params(
            self,
            step_class,
            config_params,
            step_id
    ):
        """
        Check parameter against step class definitions, use defaults if
        required parameter are not filled in.
        """
        cleaned_params = {}
        for key in config_params:
            # it's possible a parameter key was misspelled etc., we don't want
            # people to think their config file is working as expected when a
            # default is being set instead
            if key not in step_class.params:
                self.config_problems.append(f"Unknown param '{key}' in "
                                            f"{step_id}.")

        for key, param in step_class.params.items():
            if key in config_params:
                value = config_params[key]
            elif param.required:
                if param.default is not None:
                    # if required, use an existing default
                    # may want to add hardware config check here?
                    value = param.default
                else:
                    # no default for required param that wasn't set
                    self.config_problems.append(f"Param '{key}' is required "
                                                f"in {step_id}, there are no"
                                                f" defaults.")
                    continue
            else:
                # if it's not required & not set, we don't care about it
                continue
            value, problem = param.check(value)
            if problem:
                self.config_problems.append(f"Param '{key}' in {step_id}: "
                                            f"{problem}")
            cleaned_params[key] = value
        return cleaned_params


def write_config(pipeline_config):
    # write config file in yaml format
    # from PipelineConfig class
    return


def read_yaml(yaml_path):
    if not yaml_path.is_file():
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