"""
Serial communication using the module "serial"
"""
from typing import List, Literal, Optional
import serial  # type: ignore # pylint: disable=import-error
from .serial_params import EIGHTBITS, PARITY_NONE, STOPBITS_ONE


class SerialDriver():
    """
    Base class for serial drivers
    """

    lf = "\r\n"

    def __init__(self,
                 logical_name,
                 address,
                 simulate,
                 baudrate=9600,
                 bytesize=EIGHTBITS,
                 parity=PARITY_NONE,
                 stopbits=STOPBITS_ONE,
                 timeout=1,
                 dsrdtr=False,
                 xonxoff=False,
                 rtscts=False):

        self.logical_name = logical_name
        self.address = address
        self.simulate = simulate

        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self.dsrdtr = dsrdtr
        self.xonxoff = xonxoff
        self.rtscts = rtscts

        self.open()

    def get_driver(self, **kwds):
        """ Gets serial.Serial driver with **kwds. """
        return serial.Serial(**kwds)

    def send(self, command: str):
        """ Sends a command + line_end encode with ascii. """
        self.serial.write((command + self.lf).encode('ascii'))

    def send_rawdata(self, command: str):
        """ Sends a raw command. No line_end, no encoding. """
        self.serial.write(command)

    def readline(self):
        """ Reads a line from the serial. """
        return self.serial.readline()

    def read_rawdata(self):
        """runs serial.read()"""
        return self.serial.read()

    def close(self):
        """ Closes the serial connection. """
        self.serial.close()

    def open(self) -> Literal[True]:
        """ Open the serial connection. Returns True if done. """
        self.serial = self.get_driver(port=self.address,
                                      baudrate=self.baudrate,
                                      bytesize=self.bytesize,
                                      parity=self.parity,
                                      stopbits=self.stopbits,
                                      timeout=self.timeout,
                                      dsrdtr=self.dsrdtr,
                                      xonxoff=self.xonxoff,
                                      rtscts=self.rtscts)
        return True

    def ask(self, command: Optional[str] = None) -> str:
        """ Asks command string if provided and returns the response.
        With None as command return just the response."""
        if command:
            self.send(command)
        return (self.readline().strip())

    @classmethod
    def supported_models(cls) -> List[str]:
        """
        Returns the list of models supported by this driver. The
        model is the string between the first and second "," in the
        *IDN? query reply.
        """

        models = []
        if hasattr(cls, '_supported_models'):
            return cls._supported_models  # type: ignore
        for child in cls.__subclasses__():
            models += child.supported_models()
        return models
