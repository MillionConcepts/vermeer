

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

    all_steps = {}
    params = {}
    inputs = ()
    outputs = ()

    def __init__(self, name, params, hardware):
        self.name = name
        self.hardware = hardware
        for key, value in params.items():
            setattr(self, key, value)

    def __init_subclass__(cls, **kwargs):
        """ For every step subclass, load to step registry."""
        super().__init_subclass__(**kwargs)
        name = "".join("_" + c.lower() if c.isupper()
                       else c for c in cls.__name__)
        cls.step_name = name.lstrip("_")
        # this is how we check if a step is a real step
        Step.all_steps[cls.step_name] = cls

    def run(self, **inputs):
        result = self.process(**inputs)
        # check outputs here?
        return result

    # def describe():
    #     # Describe inputs / outputs / parameters of each step for cli
    #     return