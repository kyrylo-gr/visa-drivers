"""
Visa communication using the module "visa"
"""

# from pyhardware.drivers import Driver
import visa  # type: ignore


class VisaDriver():
    """
    Base class for device interfaced with Visa
    """

    def __init__(self, logical_name, address, simulate, **kwds):
        """
        args are logical_name, address, simulate
        """
        # super(VisaDriver, self).__init__(*args)

        self.logical_name = logical_name
        self.address = address
        self.simulate = simulate

        try:
            self.visa_instr = visa.instrument(self.address, **kwds)
        except AttributeError:  # visa version > 1.8
            self.visa_instr = visa.ResourceManager().get_instrument(self.address, **kwds)

    def ask(self, val):
        """ Asks the driver """
        return self.visa_instr.ask(val).strip()

    def read(self):
        """ Reads a response """
        return self.visa_instr.read().strip()

    def write(self, val):
        """ Sends val to instrument """
        return self.visa_instr.write(val)

    @classmethod
    def supported_models(cls):
        """
        returns the list of models supported by this driver. The
        model is the string between the first and second "," in the
        *IDN? query reply.
        """

        models = []
        if hasattr(cls, '_supported_models'):
            return cls._supported_models  # type: ignore
        for child in cls.__subclasses__():
            models += child.supported_models()
        return models
