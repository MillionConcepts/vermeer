# loose steps:

# label validation section, ppl may want to examine the results of stp 2
# 1. check label is valid: YAML we can read, keywords we know, required
#    keywords present etc
#       * could we edit the YAML to easily point out what's wrong with it?
#       * Zack's work may be useful here
# 2. fill in missing parts of the label that have defaults / are not required
#    to be input by the user but are needed for a run
# dry run validation section
# 3. check all required files that won't be made by the imaging chain exist
# 4. check all required files will exist by the time a step needs them
#       * it would be nice if step 4 could be printed out in a pretty chart
#          to show why someone's configuration might not work etc
# 5. check that each step can be run for the specific hardware configuration
#    given? kind of same thing as check required cal files
# run section
# 6. assign a random run ID (this could happen at step 2 tbh)
# 7. make a folder for this random run ID for outputs or intermediate products
# 8. step by step, read input, apply calibration, validate completion,
#    write relevant outputs, retain intermediate products / outputs as
#    requested
from typing import Literal

def execute_pipeline(
    run_type: Literal["validate", "run"],
    config_file: str,
    verbose: bool = False,
):
    from config_file import PipelineConfig

    # build PipelineConfig class from config file
    pipeline_config = PipelineConfig(config_file)

    if pipeline_config.config_problems:
        # write problems to an output file. if there are errors just reading
        # the config file, those will have raised a ConfigError
        if verbose:
            print(f"Problems were identified while validating the config file."
                  f" Writing pipeline problems to "
                  f"{pipeline_config.problem_report_path}.")
        pipeline_config.write_problems()

    # write modified config / config to be used by pipeline out as well
    if verbose:
        print(f"Writing the modified config file to "
              f"{pipeline_config.modified_config_path}.")
    #TODO: make a writer to output the modified config / pipeline_config
    # in YAML format that's 1:1 with input (ie we could read it back in).
    # some attributes would have to be ignored? like run_id? not sure what to
    # do about that.

    if run_type == "validate":
        # exit here, we don't want to actually run the pipeline
        return 1

    if run_type == "run":
        return run_pipeline(pipeline_config)

    return None


def run_pipeline(pipeline_config):
    # loop through steps in pipeline_config, writing outputs as needed
    # also do logging
    return 1




