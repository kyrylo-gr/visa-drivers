"""
Info about the commands :
https://rfmw.em.keysight.com/wireless/helpfiles/89600B/WebHelp-scpi/scpiref.htm#CSHID=undefined

"""
# pylint: disable=import-error
from typing import List, Literal, Optional, Tuple
import logging
import os.path as osp
import numpy as np
import pyvisa as visa  # type: ignore
from pyvisa.errors import VisaIOError  # type: ignore
from ..async_utils import sleep


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class RSVectorAnalyser(object):  # , FetcherMixin):
    """VSA object"""
    _supported_models = ["FPL1000"]
    _delay = 0.3

#    VSA_ROOT = '//leon.lkb.upmc.fr/OMQ/PillarExperiment2017/cryoscripts/vsa/'

    VSA_ROOT = 'C:\\Users\\Public\\Documents\\Rohde-Schwarz\\Analyzer\\user\\'

    def __init__(self, port, *args, **kwds):  # pylint: disable=unused-argument
        #self.net_instr = Vsa()
        #super(VSA, self).__init__(*args, **kwds)

        self.visa_instr = visa.ResourceManager().get_instrument(port)
        self.visa_instr._encoding = 'latin1'  # to decode massages with accents

    def ask(self, query: str) -> str:
        """Send query to the instrument"""
        return self.visa_instr.query(query).strip().replace('"', '')

    def write(self, value) -> None:
        """Write value to the instrument"""
        return self.visa_instr.write(value)

    def instr_create(self,
                     mode: Literal['SAN', 'ADEM', 'IQ', 'NOISE', 'DDEM'],
                     name: str = "Python") -> None:
        """RS VA has different types of windows. Instrument is actually a tab window inside VA"""
        self.write(f"INST:CRE {mode}, '{name}'")

    def instr_current(self) -> Tuple[Literal['SAN', 'ADEM', 'IQ', 'NOISE', 'DDEM'], str]:
        """Getting current instrument (=tab windows).
        Returns type and name of the instrument."""
        query_answer = self.ask("INSTrument?")
        instr_lst = self.instr_list()
        for type_, name_ in instr_lst:
            if query_answer == type_ or query_answer == name_:
                return (type_, name_)

        raise ValueError(
            f"Cannot get current instrument from query INSTrument? ={query_answer}")

    def instr_current_mode(self) -> Literal['SAN', 'ADEM', 'IQ', 'NOISE', 'DDEM']:
        """Returns mode of the current instrument"""
        return self.instr_current()[0]

    def instr_current_name(self) -> str:
        """Returns name of the current instrument"""
        return self.instr_current()[1]

    def instr_list(self) -> List[
            Tuple[Literal['SAN', 'ADEM', 'IQ', 'NOISE', 'DDEM'], str]]:
        """Return list of existing instruments."""

        known_types = ('SAN', 'ADEM', 'IQ', 'NOISE', 'DDEM')
        val = self.ask("INSTrument:LIST?").split(',')
        lst: List[tuple] = []
        for instr_type, instr_name in zip(val[::2], val[1::2]):
            for known_type in known_types:
                if known_type.lower() in instr_type.lower():
                    instr_type = known_type
                    break
            else:
                raise ValueError(
                    f"Unknown type of instr. type {instr_type} named {instr_name} is not in list of types.")

            lst.append((instr_type, instr_name.strip()))

        return lst

    def instr_exist(self, name: str) -> bool:
        """Returns True if the instrument with name exists"""
        instr_lst = self.instr_list()
        for _, instr_name in instr_lst:
            if instr_name.lower() == name.lower():
                return True
        return False

    def instr_select(self, name: str) -> None:
        """Select the instrument with the given name"""
        self.write(f"INSTrument:SELect {name}")

    def instr_delete(self, name: Optional[str] = None) -> None:
        """Delete the instrument with the given name"""
        if name is None:
            name = self.instr_current_mode()
        self.write(f"INSTrument:DELete {name}")

    @property
    def idn(self):
        """Get the id of the instrument"""
        return self.ask('*IDN?')

    def clear_errors(self) -> List[str]:
        """Clear and print all errors from the instrument"""
        errors = []
        while True:
            error = self.error
            if "No error" in error or len(error) == 0:
                return errors
            errors.append(error)
            logger.warning("There was an error: %s", error)

    def preset(self) -> None:
        """ Run the preset and restart"""
        self.write(':SYSTem:PRESet')
        self.restart()

    def reset(self) -> None:
        """Reset the instrument and restart. Equivalent to preset and sweep_single in the row"""
        self.write('*RST')
        self.restart()

    def immediately(self) -> None:
        """Perform the measurement. The same function as restart"""
        self.write("INITiate:IMMediate")

    def restart(self) -> None:
        """Restart the measurement. The same function as immediately"""
        self.immediately()

    def abort(self) -> None:
        """Abort the measurement"""
        self.write("INITiate:SEQuencer:ABORt")

    def sweep_continuous(self) -> None:
        """Take the measurements continuously"""
        self.write("INITiate:CONTinuous ON")

    def sweep_single(self) -> None:
        """Take only one measurement"""
        self.write("INITiate:CONTinuous OFF")
        self.restart()

    def _recall(self, filename) -> None:
        """Clean all error and load the setup from the file."""
        # raise NotImplementedError()
        self.clear_errors()
        self.write("MMEM:LOAD:TYPE REPLace")
        self.write(f"MMEM:LOAD:STAT 1,'{filename}'")
        err = self.error
        if "No error" not in err:
            raise BaseException(f"Error in recall {filename} to VSA: {err}")

    def recall(self, filename) -> None:
        """Putting filename to right format. Clean all errors and load the setup file"""
        filename = osp.join(self.VSA_ROOT, filename)
        self._recall(filename)

    def instr_activate(self, name: str):
        """Check if the instrument with the given name exists and activate it if True"""
        if self.instr_exist(name):
            self.instr_select(name)
        else:
            self.recall(name)

    def _store(self, filename) -> None:
        """ Store current to filename """
        raise NotImplementedError()
        # self.write(f':MMEMory:STORe:SETup "{filename}"')

    def store(self, filename) -> str:
        """ Store current setup to file. returns fullpath """
        filename = osp.join(self.VSA_ROOT, filename+'.setx')
        self._store(filename)
        return filename

    @property
    def error(self) -> str:
        """ Return next error message """
        return self.ask(':SYSTem:ERRor:NEXT?')

    @property
    def status(self) -> int:
        """ Get strange number that corresponds to the status """
        return int(self.ask('STATus:OPERation:CONDition?'))

    @property
    def frequency(self) -> float:
        """Get the central frequency"""
        val = self.ask("SENSe:FREQuency:CENTer?")
        return float(val)

    @frequency.setter
    def frequency(self, val: float) -> None:
        """Set the central frequency"""
        self.write(f"SENSe:FREQuency:CENTer {val:f}")

    # center is identical with frequency, but sometimes more intuitive
    @property
    def center(self) -> float:
        """ Returns the self.frequency """
        return self.frequency

    @center.setter
    def center(self, val: float) -> None:
        """ Sets the self.frequency """
        self.frequency = val

    @property
    def start(self) -> float:
        """ Gets the start of the frequencies """
        val = self.ask("SENSe:FREQuency:STARt?")
        return float(val)

    @start.setter
    def start(self, val: float) -> None:
        """ Sets the start of the frequencies """
        self.write(f"SENSe:FREQuency:STARt {val:f}")

    @property
    def stop(self) -> float:
        """ Gets the end of the frequencies """
        val = self.ask("SENSe:FREQuency:STOP?")
        return float(val)

    @stop.setter
    def stop(self, val: float) -> None:
        """ Sets the end of the frequencies """
        self.write(f"SENSe:FREQuency:STOP {val:f}")

    @property
    def span(self) -> float:
        """ Gets the span of the frequencies """
        val = self.ask("SENSe:FREQuency:SPAN?")
        return float(val)

    @span.setter
    def span(self, val: float) -> None:
        """ Sets the span of the frequencies """
        self.write(f"SENSe:FREQuency:SPAN {val:f}")

    def save_config(self, filename: str) -> None:
        """ Save the config file """
        raise NotImplementedError()
        # self.write(f'MMEMORY:STORE "{filename}"')

    def load_config(self, filename: str, path: Optional[str] = None) -> None:
        """ Load the config file """
        raise NotImplementedError()
        # if path is None:
        #     path = self.VSA_ROOT
        # filename = "/"
        # self.write(f'MMEMORY:LOAD "{path}/{filename}"')

    # @property
    # def rbw_couple(self) -> Literal['Auto', 'Offset', 'Fixed']:
    #     """Gets how ResBW is coupled to the frequency span."""
    #     val = self.ask("SENSe:RBW:COUPle?")
    #     return val  # type: ignore

    # @rbw_couple.setter
    # def rbw_couple(self, val: Literal['Auto', 'Offset', 'Fixed']) -> None:
    #     """Sets how ResBW is coupled to the frequency span: 'Auto','Offset','Fixed'"""
    #     self.write(f"SENSe:RBW:COUPle '{val}'")

    def get_format(self
                   ) -> Tuple[Literal["ASCii", "REAL"], Literal[0, 16, 32, 64]]:
        """ Gets the result's format."""
        return self.ask("FORMat:DATA?").split(",")  # type: ignore

    def set_format(
            self, form: Literal["ASCii", "REAL"], bit_length: Literal[0, 16, 32, 64] = 32) -> None:
        """ Sets the result's format."""
        self.write(f'FORMat:DATA {form} {bit_length}')

    def get_iq_format(self) -> Literal['COMP', 'IQBL', 'IQP']:
        """
        This command selects the order of the I/Q data.

        COMPatible
        I and Q values are separated and collected in blocks:
        A block (512k) of I values is followed by a block (512k) of Q values,
        followed by a block of I values, followed by a block of Q values etc.
        (I,I,I,I,Q,Q,Q,Q,I,I,I,I,Q,Q,Q,Q...)

        IQBLock
        First all I-values are listed, then the Q-values
        (I,I,I,I,I,I,...Q,Q,Q,Q,Q,Q)

        IQPair
        One pair of I/Q values after the other is listed
        (I,Q,I,Q,I,Q...).
        """
        return self.ask("TRACe:IQ:DATA:FORMat?")  # type: ignore

    def set_iq_format(self, form: Literal['COMP', 'IQBL', 'IQP']) -> None:
        """Set the format of the output data when instrument in mode IQ"""
        return self.write(f"TRACe:IQ:DATA:FORMat {form}")

    @property
    def rbw(self) -> float:
        """ Gets the resolution bandwidth (RBW), in Hertz. """
        val = self.ask("SENSe:BWIDt:RESolution?")
        return float(val)

    @rbw.setter
    def rbw(self, val: float) -> None:
        """ Sets the resolution bandwidth (RBW), in Hertz. """
        # self.rbw_couple = "Fixed"
        self.write(f"SENSe:BWIDt:RESolution {val:f}")

    @property
    def points(self) -> int:
        """ Gets the number of unaliased frequency points to display. """
        val = self.ask("SENSe:SWEep:POINts?")
        return int(val)

    @points.setter
    def points(self, val: int) -> None:
        """ Sets the number of unaliased frequency points to display. Maximum is 409601. """
        self.write(f"SENSe:SWEep:POINts {val:f}")

    # @property
    # def points_auto(self) -> bool:
    #     """ Sets a value indicating whether the number of
    #     frequency points is automatically adjusted to accommodate
    #     a larger range of ResBW values (0:False, 1:True)"""
    #     val = self.ask("SENSe:RBW:POINts:AUTO?")
    #     val = int(val)
    #     if val == 0:
    #         return False
    #     else:
    #         return True

    # @points_auto.setter
    # def points_auto(self, val: bool) -> None:
    #     """ Sets the points automatically """
    #     if val:
    #         val_int = 1
    #     else:
    #         val_int = 0
    #     self.write(f"SENSe:RBW:POINts:AUTO {val_int}")

    @property
    def average(self) -> int:
        """ Gets a number of sweeps is taken per measurement """
        val = self.ask("SENSe:AVERage:COUNt?")
        return int(val)

    @average.setter
    def average(self, val: int) -> None:
        """ Specifies a number of sweeps is taken per measurement """
        if val > 1:
            self.write("SENSe:AVERage ON")
        else:
            self.write("SENSe:AVERage OFF")

        self.write(f"SENSe:AVERage:COUNt {val:.0f}")

    # @property
    # def average_repeat(self) -> bool:
    #     """ Gets whether the averaged measurement is repeated. """
    #     val = int(self.ask("SENSe:AVERage:REPeat?"))
    #     return (val != 0)

    # @average_repeat.setter
    # def average_repeat(self, val: bool) -> None:
    #     """ Sets whether the averaged measurement is repeated. """
    #     self.write(f"SENSe:AVERage:REPeat {val:d}")

    @property
    def average_style(self) -> Literal["VID", "LOG", "LIN", "POW"]:
        """ Gets the average style:
        LOGarithmic
        The logarithmic power values are averaged.

        LINear
        The power values are averaged before they are converted to logarithmic values.

        POWer
        The power level values are converted into unit Watt prior to averaging.
        After the averaging, the data is converted back into its original unit.
        """
        val = self.ask("SENSe:AVERage:TYPE?")
        return val  # type: ignore

    @average_style.setter
    def average_style(self, val: Literal["VID", "LOG", "LIN", "POW"]) -> None:
        """ Sets the average style: """
        self.write(f'SENSe:AVERage:TYPE "{val}"')

    # @property
    # def current_average(self, trace: int = 1) -> int:
    #     """ Current acquisition number of measurements that were already performed. """
    #     val = self.ask(f":TRACe{trace}:DATA:HEADer? 'CurrentNumAverages'")
    #     return int(val) if len(val) > 0 else 0

    # @property
    # def is_average_done(self) -> bool:
    #     """ Checks if the number of measurements taken is equal to the desired number of average. """
    #     return self.current_average >= self.average  # normally is should be never bigger.

    def wait_average_done(self) -> None:
        """ Loops until average is finished. """
        while not self.measurement_ready:
            sleep(self._delay)

    @property
    def measurement_done(self) -> bool:
        """ Returns True if all the current overlapped commands are completed """
        previous_timeout = self.visa_instr.timeout
        self.visa_instr.timeout = 60000  # 6s
        try:
            self.ask("*OPC?")  # Returns 1 if completed or doesn't return
        except VisaIOError:
            self.visa_instr.timeout = previous_timeout
            return False

        self.visa_instr.timeout = previous_timeout
        return True

    @property
    def measurement_ready(self) -> bool:
        """ Returns True if the current status is 'done' """
        return self.status == 0

    @property
    def time_length(self) -> float:
        """ Returns the time it takes to measure """
        return float(self.ask("SENSe:SWEep:TIME?"))

    @time_length.setter
    def time_length(self, val: float):
        """ Sets the measurement time length """
        self.write(f"SENSe:SWEep:TIME {val:f}")

    def wait_measurement_done(self, sleep_function=None, delay=None) -> bool:
        """ Waits till the measurement is done (and returns True) or
        till the sleep_function returns False (and then returns False). """

        if delay is None:
            delay = self._delay
        if sleep_function is None:
            sleep_function = sleep

        while not self.measurement_done:
            sleep_result = sleep_function(delay)
            if sleep_result is False:
                return False
        return True

    def _visa_get_data(self, trace: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """ Gets the data in LinearMagnitude format. """

        # backup_format = self.get_format(trace=trace)  # backup format

        self.set_format('ASCii')

        query = self.ask(f"TRACe:DATA:X? TRACe{trace:d}")
        data_x = np.array([float(d) for d in query.split(",")])
        query = self.ask(f"TRACe:DATA? TRACe{trace:d}")
        data_y = np.array([float(d) for d in query.split(",")])

        # self.set_format(backup_format, trace=trace)  # restore format
        return data_x, data_y

    def _visa_get_data_complex(self, trace: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """ Gets the complex data in (Real + 1j Imag) format. """

        # backup_format = self.get_format(trace=trace)

        self.set_iq_format('IQBL')

        query = self.ask(f"TRACe:DATA:X? TRACe{trace:d}")
        data_x = np.array([float(d) for d in query.split(",")])

        data = self.ask("TRACe:IQ:DATA:MEMory?").split(",")
        data_y = np.array([float(re) + 1j*float(im) for (re, im) in zip(
            data[:len(data)//2], data[len(data)//2:])])

        # self.set_format(backup_format, trace=trace)
        return data_x, data_y

    # @property
    # def time_resolution_auto(self) -> bool:
    #     """ Gets a value indicating whether the span is adjusted to achieve specified main time length. """
    #     return int(self.ask(":SENSe:TIME:RESolution:AUTO?")) == 1

    # @time_resolution_auto.setter
    # def time_resolution_auto(self, val: str) -> None:
    #     """ Sets a value indicating whether the span is adjusted to achieve specified main time length. """
    #     self.write(f":SENSe:TIME:RESolution:AUTO {val:d}")

    def get_curve(self, trace: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """ Gets the data in LinearMagnitude format. """
        return self._visa_get_data(trace)

    def get_curve_complex(self, trace: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """ Gets the complex data in (Real + 1j Imag) format. """
        return self._visa_get_data_complex(trace)

    def single(self, trace: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """ Run measurement, wait until done and return the result. """
        self.immediately()
        self.wait_measurement_done()
        return self.get_curve(trace)

    def single_complex(self, trace: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """ Run measurement, wait until done and return the result. """
        self.immediately()
        self.wait_measurement_done()
        return self.get_curve_complex(trace)

    # @property
    # def input_range_peak(self) -> float:
    #     """ Gets the input range (in Vpk) of the input channel. """
    #     return float(self.ask(':INPut:ANALog:RANGe?'))

    # @input_range_peak.setter
    # def input_range_peak(self, val: float) -> None:
    #     """ Sets the input range (in Vpk) of the input channel. """
    #     self.write(f':INPut:ANALog:RANGe {val:f}')

    # @property
    # def input_range_dbm(self) -> float:
    #     return 10 * np.log10((self.input_range_peak / np.sqrt(2)) ** 2 / 50) + 30

    # @input_range_dbm.setter
    # def input_range_dbm(self, val: float) -> None:
    #     power = 10 ** ((val / 10) - 3)
    #     self.input_range_peak = np.sqrt(2 * power * 50)

    # def enable_marker(self, trace: int, marker_number: int) -> None:
    #     """ Enables the marker. """
    #     self.write(f':TRACE{trace:d}:MARK{marker_number:d}:ENABLE 1')

    # def disable_marker(self, trace: int, marker_number: int) -> None:
    #     """ Disables the marker. """
    #     self.write(f':TRACE{trace:d}:MARK{marker_number:d}:ENABLE 0')

    # def set_marker_x_position(self, trace: int, marker_number: int, pos: float) -> None:
    #     """ Sets the marker position."""
    #     self.write(f':TRACE{trace:d}:MARK{marker_number:d}:X {pos:f}')

    # def set_marker_type(self, trace: int, marker_number: int, marker_type: str) -> None:
    #     """ Sets the marker type. Possible values are "Normal" | "Delta" | "Fixed """
    #     self.write(f':TRACE{trace:d}:MARK{marker_number:}:TYPE {marker_type}')

    # def get_marker_y_position(self, trace: int, marker_number: int) -> float:
    #     """ Gets the y value of the marker. """
    #     return float(self.ask(f':TRACE{trace:d}:MARK{marker_number:d}:Y?'))

    # def trace_xunit(self, trace: int = 1) -> str:
    #     """ Returns unit of X axis. """
    #     return self.ask(f':TRACe{trace:d}:X:SCALe:UNIT?')

    # def trace_yunit(self, trace: int = 1) -> str:
    #     """ Returns unit of Y axis. """
    #     return self.ask(f':TRACe{trace:d}:Y:SCALe:UNIT?')

    # def trace_valid(self, trace: int = 1) -> bool:
    #     """ Gets if the data for this trace is valid. """
    #     return self.ask(f':TRACe{trace:d}:DATA:VALid?') == '1'

    # @property
    # def trace_count(self) -> int:
    #     """ Gets the number of items in the collection. """
    #     return int(self.ask(":TRACe:COUNt?"))

    # @property
    # def measure_count(self) -> int:
    #     """ Number of measurements loaded in the VSA. """
    #     return int(self.ask("MEASure:COUNt?"))

    # def measure_remove(self) -> None:
    #     """ Remove a measurement from the collection. """
    #     self.write(":MEASure:REMove")

    # def measure_add(self) -> None:
    #     """ Creates a new vector measurement. """
    #     self.write(":MEASure:ADD")  # Creates a new vector measurement.
    #     self.write(":MEASure:CONFigure VECTor")  # Sets the active measurement type.
    #     self.write(":TRACe:REMove:LAST")  # Remove the last trace from the trace collection.

    #     # Arranges the trace windows on the display. param: row, column
    #     self.write(f":DISPlay:LAYout 1, {self.measure_count}")

    def measure_select(self, meas: str) -> None:
        """ Select a measurement from the collection. """
        self.write(f":MEASure:SELect {meas}")

    # : VSA BASE FUNCTIONS in the class itself

    def take_sample_curve(self) -> Tuple[np.ndarray, np.ndarray]:
        """ Measures with current setup but with average turn off. Return freq, vals. """
        # avg_repeat_status = self.average_repeat
        # self.average_repeat = False
        curve = self.single(1)
        # self.average_repeat = avg_repeat_status
        return curve

    def take_sa_curve_vi_error_robust(self, n_retry: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """ Performs a single measurement without averaging.
        Robust to VI timeouts (repeats the measurements n_retry times). """
        while True:
            try:
                n_retry -= 1
                return self.take_sample_curve()
            except Exception as error:  # pylint: disable=broad-except
                logger.warning("Error during take sa_curve. Error: %s", error)
                if n_retry < 0:
                    raise error

    def recall_state_vi_error_robust(self, filename, n_retry: int = 10) -> None:
        """ Recalls the state from filename.
        Robust to VI timeouts (repeats the measurements n_retry times). """
        while True:
            try:
                n_retry -= 1
                self.recall(filename=filename)
                return
            except Exception as error:  # pylint: disable=broad-except
                logger.warning("Error during take sa_curve. Error: %s", error)
                if n_retry < 0:
                    raise error
