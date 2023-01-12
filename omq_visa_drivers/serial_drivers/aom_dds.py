import sys
from typing import Literal
import numpy as np
from .serial_driver import SerialDriver
from .serial_params import EIGHTBITS, PARITY_NONE, STOPBITS_ONE


class AOM_DDS(SerialDriver):  # pylint: disable=invalid-name
    """Serial driver for AOM or EOM"""
    _supported_models = ["AOM_DDS"]

    def __init__(self, *args, **kwds):
        kwds = {"baudrate": 9600,
                "bytesize": EIGHTBITS,
                "parity": PARITY_NONE,
                "stopbits": STOPBITS_ONE,
                "timeout": 1,
                "dsrdtr": False}

        self._device: Literal[0, 1] = 0
        self.device = 0
        super().__init__(*args, **kwds)
        #self.ser = serial.Serial(port = device, baudrate = 9600, bytesize = serial.SEVENBITS,
        #       parity = serial.PARITY_EVEN, stopbits = serial.STOPBITS_TWO, timeout= 0.5, dsrdtr = 1)
        # print self.ser
        # self.send("*IDN?")
        # print "DEVICE: " + self.ser.readline()
        # self.send("*RST")
        # self.send("*CLS")

    @property
    def device(self) -> Literal[0, 1]:
        return self._device

    @device.setter
    def device(self, value: Literal[0, 1]) -> None:
        if value in (0, 1):
            self._device = value
        else:
            raise ValueError("Unacceptable value. Possible values are [0, 1]. Device remains : ", self._device)

    @property
    def frequency(self) -> float:
        answer = self.ask(':C0')
        if self.device == 0:
            freq_value = int(answer[6:14], base=16)
        elif self.device == 1:
            freq_value = int(answer[17:25], base=16)
        else:
            raise KeyError("Unacceptable device number is set.")
        return float(freq_value)*500e6/float(int('7FFFFFFF', base=16))

    @frequency.setter
    def frequency(self, freq: float) -> None:
        freq_value = int(np.round(float(freq)/500e6*float(int('7FFFFFFF', base=16))))
        str_to_send = f":L{self.device:1d}G{freq_value:8x}"
        self.ask(str_to_send)


if __name__ == "__main__":
    ea = AOM_DDS(sys.argv[1])
