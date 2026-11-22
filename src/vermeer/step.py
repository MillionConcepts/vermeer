

class Param:
    def __init__(self, type, options=None, is_file=False):
        self.type = type
        self.options = options
        self.is_file = is_file

    def check(self, val):
        if type(val) is not self.type:
            return val, (f"expected {self.type.__name__}, "
                         f"got {type(val).__name__}.")
        if self.options and val not in self.options:
            return val, f"{val} not in list of options: {self.options}."
        return val, None

class Step:
    """Base class for processing steps. Based on STPIPE Step Class for JWST."""

    all_steps = {} # how to gather all steps somewehere? stpipe uses an aggregator
    params = {}
    inputs = ()
    outputs = ()

    def __init__(self, name, params, hardware):
        self.name = name
        self.hardware = hardware
        for key, value in params.items():
            setattr(self, key, value)

    def run(self, **inputs):
        result = self.process(**inputs)
        # check outputs here?
        return result

    # def describe():
    #     # Describe inputs / outputs / parameters of each step for cli
    #     return