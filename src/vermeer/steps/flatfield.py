
from ..step import Step, Param
from ..datamodel import DataModel # doesn't exist yet

class FlatField(Step):
    """ Flat field an image using a pre-existing flat field."""
    params = {
        'flatfield': Param(str, is_file=True),
        'flat_op': Param(str, options=("multiply", "divide")),
    }
    inputs = {'image'}
    outputs = {'image'}

    def process(self, image):
        flat = DataModel.read(self.flatfield).data  # will open flat file with pdr probs
        if self.flat_op == 'multiply':
            data = image.data * flat
        elif self.flat_op == 'divide':
            data = image.data / flat
        return {"image": DataModel(data, image.meta)}

# class MakeFlatField(Step):
#     """ Make a flat field from inputs."""