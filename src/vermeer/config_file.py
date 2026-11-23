
from pathlib import Path
import pyyaml as yaml
from . import steps
from .step import Step
from . import __version__, SCHEMA_DIR
from errors import ConfigError


class PipelineConfig:
    """
    Class for the configuration of a whole run. Stores and adds to pipeline
    configurations indicated in the original config file. Supplements with
    defaults in hardware config file or
    """

    def __init__(self, config_file):

        # generate random run ID version here?
        # self.run_ID =

        self.config_file = Path(config_file)
        self.config_problems = []

        config = read_yaml(self.config_file)

        # load yaml schema file
        self.schema_version = str(config.get("yaml_schema_version"))
        self.schema_path = SCHEMA_DIR / f"config_schema_{self.schema_version}.yaml"
        self.schema = read_yaml(self.schema_path)

        # CHECK config against schema, then set attributes based on config
        # check type & if required or not
        for key in config etc

        # check config steps against step subclasses, set default
        # Each processing step listed gets loaded
        step_list = config.get("calibration_steps")
        if not step_list:
            self.config_problems.append("calibration_steps is empty, there"
                                        "are no processing steps to run.")

        self.steps = []
        # 0 index or 1 index steps?
        for position, step in enumerate(step_list, start=1):
            self.add_step(position, step)



        # Alert to all problems gathered
        if self.problems:
            raise SOMETHING


        def add_step(self, position, step):
            # id is different from step name, bc for some reason you may want
            # to run the same step twice and therefore calling them different
            # things could be helpful. for example, if you have two different
            # flat fields, one lab and one obs flat. you might call the step_id
            # for flat_field, 'lab_flat' and 'obs_flat'
            step_id = step.get("id")
            step_name = step.get("step")

            for key in step:
                # KEYS FROM SCHEMA file? but that doesn't make sense
                # because we have a Step class

            if step_id in [s.name for s in self.steps]:
                self.problems.append(f"step ID {step_id} is used twice")

            # add check that step is a real step in Step class
            step_class = Step.all_steps.get(step_name)
            params =  # function to check / get params
            inputs =  # function to check / get inputs
            outputs = # function to check / get outputs
            retain =  # function to check retain (can it be retained? etc)
            self.steps.append(step_class(step_id, params, self.hardware, inputs, outputs,
                           retain))

            # the functions to check params, inputs, outputs etc
            # should be adding the defaults from hardware and then the step
            # subclass where applicable if not already set in the config file
            # report any problems to "self.config_problems)


def write_config(pipeline_config)
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
