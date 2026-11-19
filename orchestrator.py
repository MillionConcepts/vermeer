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

