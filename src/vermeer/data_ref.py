

class DataRef:
    """
    Class for holding information about input or output files used / produced
    by the pipeline. Doesn't hold the data itself, but is a reference for
    writing it, keeping it in memory, paths, etc.
    """
    def __init__(self, path, made_by=None, write=True, retain=False):
            self.path = path        # where it's stored or where to write it
            self.made_by = made_by  # step that outputs this, None if pre-made
            self.used_by = []     # every step that takes this as input
            self.write = write    # write after making?
            self.retain = retain  # keep in memory?


