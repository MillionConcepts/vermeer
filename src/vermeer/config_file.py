
from pathlib import Path
import yaml
from . import steps
from .step import Step
from . import __version__, SCHEMA_DIR
from errors import ConfigError
from datetime import datetime
from data_ref import DataRef


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

        # software version from config
        self.pipeline_software_version = config.get("pipeline_software_version")
        # add check here against __version__?

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

        # make empty manifest dict, which will hold DataRef objects for all
        # unique input / outputs defined in the steps. we add these objects to
        # the 'manifest' while loading the steps below. the keys of manifest
        # will correspond to the keys of the dict during a real pipeline run
        # that holds DataModel objects (the data itself).
        self.manifest = {}

        # check config steps against step subclasses, set default
        # Each processing step listed gets loaded
        step_list = config.get("calibration_steps") or []
        if not step_list:
            self.config_problems.append("calibration_steps is empty, there"
                                        "are no processing steps to run.")
        self.steps = []
        for position, step in enumerate(step_list, start=1):
            self.add_step(position, step)


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
            step_id = step.get("step")
        else:
            step_id = step.get("id")
        if step.get("id") in [s.id for s in self.steps]:
            self.config_problems.append(f"{step_id}: id is used twice")

        # check the steps listed are steps that exist, get Step subclass of
        # the specified step
        step_class = Step.all_steps.get(step.get("step"))
        if step_class is None:
            self.config_problems.append(f"'{step.get('step')}' step unknown.")
            return

        # load all step parameters, using defaults where required
        params = self.get_params(
                step_class,
                step['params'],
                step_id
            )
        # make DataRef object for all inputs or check for pre-existing
        inputs = self.get_inputs(
            step_class,
            step.get("inputs") or {},
            step_id
        )
        # make DataRef object for all outputs, check for errors
        outputs = self.get_outputs(
            step_class,
            step.get("outputs") or {},
            step.get("retain") or {},
            step_id,
            position
        )
        self.steps.append(step_class(
            step_id,
            params,
            inputs,
            outputs,
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
        # check config keys are in step class definition of inputs
        for key in config_inputs:
            if key not in step_class.inputs:
                self.config_problems.append(
                    f"{step_id}: Invalid input '{key}'."
                )
        # load configured or raise problem if inputs aren't present
        cleaned_inputs = {}
        for key in step_class.inputs:
            if key in config_inputs:
                ref = self.find_ref(config_inputs[key])
                ref.used_by.append(step_id)  # track which steps use the input
                cleaned_inputs[key] = ref
            else:
                self.config_problems.append(
                    f"{step_id}: Input '{key}' is required for {step_id}."
                )
                continue
        return cleaned_inputs


    def find_ref(self, input_key):
        """
        Check if an input key ref exists in the manifest, which at this point
        consists of all inputs / outputs of previous steps.
        """
        # case in which the input is the output of a previous step
        as_output = (self.default_output_directory / input_key).resolve()
        if as_output in self.manifest:
            return self.manifest[as_output]

        # check for input file in inputs folder
        path = self.find_file(input_key)

        # if an input file has already been used by a previous step, it will
        # be in the manifest
        if path not in self.manifest:
            self.manifest[path] = DataRef(path, write=False)

        self.read_as_file[as_output] = self.manifest[path]
        return self.manifest[path]
        return


    def get_outputs(
            self,
            step_class,
            config_outputs,
            config_retain,
            step_id,
            position,
    ):
        """
        Check outputs in config against step class definitions, use defaults
        if required parameters are not filled in.

        Output files may or may not be written, they also may or may not be
        kept in memory.
        """
        # check config keys are in step class definition of outputs
        for key in config_outputs:
            if key not in step_class.outputs:
                self.config_problems.append(
                    f"{step_id}: Invalid output '{key}'."
                )
        # check keys in retain are valid and true or false
        for key in config_retain:
            if key not in step_class.outputs:
                self.config_problems.append(
                    f"{step_id}: Invalid retain '{key}'."
                )
            if not isinstance(config_retain.get(key), bool):
                self.config_problems.append(
                    f"{step_id}: retain '{key}' must be true or false."
                )
        # load configured or raise problem if outputs aren't present
        cleaned_outputs = {}
        for key in step_class.outputs:
            if key in config_outputs:
                # if the config gives an output path to use
                path = (self.default_output_directory /
                        config_outputs[key]).resolve()
            else:
                # if the config doesn't give an output path to use, make unique
                # one for step & output & with a prefix
                path = self.get_output_path(position, step_id, key)
            if path in self.manifest:
                preexisting = self.manifest[path]
                if preexisting.made_by:
                    # case in which an output path is already the output path
                    # for another step
                    self.config_problems.append(
                        f"{step_id}: output '{key}' would overwrite "
                        f"{preexisting.made_by}'s output {path}"
                    )
                else:
                    # case in which an output path is already the input path
                    # for a previous step
                    self.config_problems.append(
                        f"{step_id}: output '{key}' is {path}, which "
                        f"{preexisting.used_by} already read in as input.")
                # don't make a new data ref for a preexisting one
                continue
            ref = DataRef(path, made_by=step_id, retain=config_retain.get(key))
            # add to the manifest, manifest used for checking between steps
            self.manifest[path] = ref
            # also keep it in the outputs of the step for the PipelineConfig
            cleaned_outputs[key] = ref
        return cleaned_outputs


    def get_output_path(self, position, step_id, key):
        """
        Default output paths are a combo of the step and output key defined
        by step class.

        Use output prefix at beginning if defined in config file.
        """
        prefix = getattr(self, "output_prefix", "")
        return f"{prefix}_{step_id}_{key}.fits" if prefix else \
            f"{step_id}_{key}.fits"


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
        elif "default" in rule:
            value = rule.get("default")
        else:
            # do not set a default when there is no default, and it's not
            # required (ex: output_prefix)
            continue
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