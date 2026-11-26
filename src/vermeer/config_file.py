from pathlib import Path
import yaml
from .step import Step
from . import __version__, SCHEMA_DIR
from .errors import ConfigError
from datetime import datetime
from .data_ref import DataRef

SCHEMA_TYPE_OPTIONS = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
}

class PipelineConfig:
    """
    Class for the configuration of a whole run. Stores and adds to pipeline
    configurations indicated in the original config file. Supplements with
    defaults in hardware config file or
    """

    def __init__(self, config_file):

        # generate random run ID version here? time or more random than that?
        self.run_ID = datetime.now().strftime("%Y%m%dT%H%M%SZ")

        # read config file
        self.config_file = Path(config_file)
        config = read_yaml(self.config_file)

        # problems found in the config, as a nested dict that mirrors the
        # config file. keys reflect structure of the config file.
        self.config_problems = {}
        # problem report doesn't exist at this path unless you call
        # write_problems
        self.problem_report_path = self.config_file.with_name(
            f"{self.config_file.stem}_problems.yaml"
        )
        self.modified_config_path = self.config_file.with_name(
            f"{self.config_file.stem}_modified.yaml"
        )

        # software version from config
        self.pipeline_software_version = config.get("pipeline_software_version")
        if self.pipeline_software_version != __version__:
            self.add_problem(
                "pipeline_software_version",
                problem=f"Version indicated by the config, "
                        f"{self.pipeline_software_version}, does not match"
                        f"the current software version, {__version__}."
            )

        # load yaml schema file
        self.schema_version = str(config.get("yaml_schema_version"))
        self.schema_path = SCHEMA_DIR / f"config_schema_{self.schema_version}.yaml"
        self.schema = read_yaml(self.schema_path)

        # checks basic config things, then set attributes from config
        config = self.check_config_schema(config, self.schema)

        # set dirs
        #TODO? modify output dir to point to run folder with run ID in the name?
        self.default_output_directory = config.get("default_output_directory")
        self.default_input_directory = config.get("default_input_directory")
        self.calibration_directory = config.get("calibration_directory")

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
        step_list = config.get("calibration_steps") or []
        if not step_list:
            self.add_problem(
                "calibration_steps",
                problem="There are no processing steps to run."
            )
        # build list of steps to run from calibration_steps
        self.steps = []
        for position, step in enumerate(step_list, start=1):
            self.add_step(step)

        # raise error if problems exist
        if self.config_problems:
            raise ConfigError(self.format_problems())


    def add_step(self, step):

        # check each step in the config has the required components. this is
        # a check against the config YAML schema, not each step subclass.
        # the id isn't checked yet, so fall back to the step name for problems
        where = step.get("id") or step.get("step") or "unnamed step"
        step = self.check_config_schema(
            step,
            self.schema["calibration_steps"]["step_requirements"],
            where
        )

        # step ID must be unique for each step in calibration pipeline
        if 'id' not in step.keys():
            step_id = step.get("step")
        else:
            step_id = step.get("id")
        if step.get("id") in [s.id for s in self.steps]:
            self.add_problem(
                step_id, "id",
                problem=f"'{step_id}' is used by more than one step, which is "
                        f"not allowed."
            )

        # check the steps listed are steps that exist, get Step subclass of
        # the specified step
        step_class = Step.all_steps.get(step.get("step"))
        if step_class is None:
            self.add_problem(
                step_id, "step",
                problem=f"'{step.get('step')}' is not a known step subclass."
            )
            return

        # load all step parameters, using defaults where required
        params = self.get_params(
                step_class,
                step.get("params") or {},
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
                self.add_problem(
                    step_id, "inputs", key,
                    problem=f"Not a valid input of {step_class.step_name}."
                )
        # load configured or raise problem if inputs aren't present
        cleaned_inputs = {}
        for key in step_class.inputs:
            if key in config_inputs:
                ref = self.find_ref(config_inputs[key], step_id, key)
                ref.used_by.append(step_id)  # track which steps use the input
                cleaned_inputs[key] = ref
            else:
                self.add_problem(
                    step_id, "inputs", key,
                    problem="Required input, but was not given."
                )
                continue
        return cleaned_inputs


    def find_ref(self, input_key, step_id, input_name):
        """
        Check if an input key ref exists in the manifest, which at this point
        consists of all inputs / outputs of previous steps.
        """
        # case in which the input is the output of a previous step
        is_output = (self.default_output_directory / input_key).resolve()
        if is_output in self.manifest:
            return self.manifest[is_output]

        # check if path is complete, then check for input file in given
        # inputs folder + cal folder
        path = self.find_ref_file(input_key)

        # if an input file has already been used by a previous step, it will
        # be in the manifest
        if path not in self.manifest:
            self.manifest[path] = DataRef(path, write=False)

        if not path.is_file():
        # input file cannot be found / doesn't exist from previous step
            self.add_problem(
                step_id, "inputs", input_name,
                problem=f"File {path} doesn't exist. Check spelling, "
                        f"directories, or previous step output paths."
            )

        return self.manifest[path]


    def find_ref_file(self, input_key):
        path = Path(input_key)
        for folder in (self.default_input_directory, self.calibration_directory):
            if (folder / path).is_file():
                return (folder / path).resolve()
        return path


    def get_outputs(
            self,
            step_class,
            config_outputs,
            config_retain,
            step_id
            ,
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
                self.add_problem(
                    step_id, "outputs", key,
                    problem=f"Not a valid output of {step_class.step_name}."
                )
        # check keys in retain are valid and true or false
        for key in config_retain:
            if key not in step_class.outputs:
                self.add_problem(
                    step_id, "retain", key,
                    problem=f"Not a valid output of {step_class.step_name}, "
                            f"can't retain."
                )
            if not isinstance(config_retain.get(key), bool):
                self.add_problem(
                    step_id, "retain", key,
                    problem="Retain policy must be 'true' or 'false'."
                )
        # load configured or raise problem if outputs aren't present
        cleaned_outputs = {}
        for key in step_class.outputs:
            if key in config_outputs:
                # if the config gives an output path to use
                path = (self.default_output_directory / config_outputs[key]).resolve()
            else:
                # if the config doesn't give an output path to use, make unique
                # one for step & output & with a prefix
                path = self.get_output_path(step_id, key)
            if path in self.manifest:
                preexisting = self.manifest[path]
                if preexisting.made_by:
                    # case in which an output path is already the output path
                    # for another step
                    self.add_problem(
                        step_id, "outputs", key,
                        problem=f"This output path would overwrite "
                                f"{preexisting.made_by}'s output {path}."
                    )
                else:
                    # case in which an output path is already the input path
                    # for a previous step
                    self.add_problem(
                        step_id, "outputs", key,
                        problem=f"{path} is already read in as input by "
                                f"{preexisting.used_by}."
                    )
                # don't make a new data ref for a preexisting one
                continue
            ref = DataRef(path, made_by=step_id, retain=config_retain.get(key))
            # add to the manifest, manifest used for checking between steps
            self.manifest[path] = ref
            # also keep it in the outputs of the step for the PipelineConfig
            cleaned_outputs[key] = ref
        return cleaned_outputs


    def get_output_path(self, step_id, key):
        """
        Default output paths are a combo of the step and output key defined
        by step class.

        Use output prefix at beginning if defined in config file.
        """
        prefix = getattr(self, "output_prefix", "")
        filename = f"{prefix}_{step_id}_{key}.fits" if prefix else \
            f"{step_id}_{key}.fits"
        return (self.default_output_directory / filename).resolve()


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
                self.add_problem(
                    step_id, "params", key,
                    problem=f"Not a valid param of {step_class.step_name}."
                )

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
                    self.add_problem(
                        step_id, "params", key,
                        problem="Required param, and there's no default to "
                                "use."
                    )
                    continue
            else:
                # if it's not required & not set, we don't care about it
                continue
            value, problem = param.check(value)
            if problem:
                self.add_problem(
                    step_id, "params", key,
                    problem=problem
                )
            cleaned_params[key] = value
        return cleaned_params


    def check_config_type(self, config_value, config_type):
        """
        Check type of given config against config YAML. Reference a dict
        of types written as strings because types in the YAML are written
        as strings.
        """
        # path case
        if config_type == "Path":
            if not isinstance(config_value, str):
                return config_value, (
                    f"Expected a path, got {type(config_value).__name__}."
                )
            return Path(config_value), None
        # other types that aren't paths
        if type(config_value) is not SCHEMA_TYPE_OPTIONS[config_type]:
            return config_value, (
                f"Expected {config_type}, got {type(config_value).__name__}."
            )
        return config_value, None


    def check_config_schema(self, config, schema, *keys):
        """
        Check all values expected by YML schema are in the config file, and
        warn about unexpected values.
        """
        # check for keys that aren't supposed to be in the config
        for key in config:
            if key not in schema:
                self.add_problem(
                    *keys,
                    key,
                    problem="Not in the config schema."
                )
        checked = {}
        # check for keys that should be in the config
        for key, rule in schema.items():
            if key in config:
                value = config[key]
            elif rule.get("required", False):
                self.add_problem(
                    *keys,
                    key,
                    problem="Required, but not given."
                )
                continue
            elif "default" in rule:
                value = rule.get("default")
            else:
                # do not set a default when there is no default, and it's not
                # required (ex: output_prefix)
                continue
            # check that the keys in the config have the right type
            value, error = self.check_config_type(value, rule["type"], key)
            if error:
                self.add_problem(
                    *keys,
                    key,
                    problem=error
                )
            checked[key] = value
        return checked


    def add_problem(self, *keys, problem):
        """
        Add problems to self.config_problems, can use multiple keys to indicate
        location in config_problems dict to match format of config file.

        Keys can't hold problems AND nested dicts. So, for example,
        config_problems['step_name'] can't have an error message and also hold
        parameter errors at config_problems['step_name']['params']['bias_sub'].
        """
        initial_dict = self.config_problems
        for key in keys[:-1]:
            initial_dict = initial_dict.setdefault(key, {})
        initial_dict.setdefault(keys[-1], []).append(problem)


    def write_problems(self):
        """
        Write self.config_problems to a YAML file, laid out like the config
        file, with the config file it came from at the top + version info.
        """
        problem_report = {
            "config_file": str(self.config_file),
            "config_schema_version": str(self.schema_version),
            "config_pipeline_version": str(self.pipeline_software_version),
            "pipeline_version_used": str(__version__),
            "problems": self.config_problems,
        }
        with open(self.problem_report_path, "w") as f:
            yaml.safe_dump(
                problem_report, f, sort_keys=False, default_flow_style=False
            )


def read_yaml(yaml_path):
    """Use pyyaml to read in config files, schema files etc in YAML."""
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