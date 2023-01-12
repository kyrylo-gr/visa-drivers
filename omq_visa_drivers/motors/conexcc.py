""" This module allows you to connect to a motor.

Example:
    motor: Motor = ConexCC(usb_port, max_speed)

where Motor is protocol that has such main attributes:
    def init_position_and_come_back(self) -> None:
        Initialize initial position and returns back.

    def set_enable(self) -> None:
        Enable the motor.

    def set_disable(self) -> None:
        Disable the motor.

    def move_absolute_sync(self, new_pos: float) -> None:
        Move absolute. waiting until the motor is moved.

    @property
    def cur_pos(self) -> float:
        ...

    @property
    def is_ready(self) -> bool:
        ...

It raises the exceptions that are all of type CCMotorError. So that you can catch them all.

Documentation for 'Newport.CONEXCC.CommandInterface' package can be found here:
https://www.newport.com/mam/celum/celum_assets/resources/CONEX-CC_-_Controller_Documentation.pdf#page=54
"""


import logging
import time

import sys
import os
from typing import Dict, Literal, NamedTuple, Optional, Tuple

# add dlls to path
import clr  # type: ignore # pylint: disable=import-error
sys.path.append(os.path.join(os.path.dirname(
    os.path.realpath(__file__)), r'CONEX-CC/Bin'))
clr.AddReference('Newport.CONEXCC.CommandInterface')
import CommandInterfaceConexCC  # type: ignore # noqa # pylint: disable=wrong-import-order, wrong-import-position, import-error

from ..async_utils import sleep  # pylint: disable=wrong-import-position # type: ignore # noqa

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CCMotorError(Exception):
    """ Global exception for CCMotorErrors """

    def __init__(self, message=None):
        self.message = message
        super().__init__(message)


class CCMotorStateError(CCMotorError):
    """Exception raised when stage is not ready"""

    def __init__(self, message=None):
        self.message = message
        super().__init__(message)


class CCMotorTimeoutError(CCMotorError):
    """Timeout to communicate with the motor"""

    def __init__(self, timeout: Optional[float] = None):
        self.timeout = timeout
        self.message = f"after waiting {'some' if timeout is not None else timeout} seconds \
                         the platform is still not ready for use. \
                         Check if the platform is working or if the timeout is correct"
        super().__init__(self.message)


class CCMotorRangeExceededError(CCMotorError):
    """Position asked is out of range error"""

    def __init__(self, pos: Optional[float] = None, max_pos: Optional[float] = None):
        self.pos = pos
        self.max_pos = max_pos
        self.message = '' if pos is None or max_pos is None else \
            f'requested position = {pos} is out of range = {max_pos}'
        super().__init__(self.message)


class CCMotorOtherError(CCMotorError):
    """ Some other error"""

    def __init__(self, message=None):
        self.message = message
        super().__init__(message)


class CCMotorCommunicationError(CCMotorError):
    """ Errors that comes from self.driver. """

    def __init__(self, message=None):
        self.message = message
        super().__init__(message)


class StateError(NamedTuple):
    """ Motor return information about state and error together. It's a class for this. """
    state: str
    error: str


class ConexCC:
    """Controller class for motor"""
    MAX_VELOCITY = 0.4
    READY_STATES = ('32', '33', '34', '36', '37', '38')
    POSSIBLE_STATES = {
        '0A': 'NOT REFERENCED from RESET.',
        '0B': 'NOT REFERENCED from HOMING.',
        '0C': 'NOT REFERENCED from CONFIGURATION.',
        '0D': 'NOT REFERENCED from DISABLE.',
        '0E': 'NOT REFERENCED from READY.',
        '0F': 'NOT REFERENCED from MOVING.',
        '10': 'NOT REFERENCED - NO PARAMETERS IN MEMORY.',
        '14': 'CONFIGURATION.',
        '1E': 'HOMING.',
        '28': 'MOVING.',
        '32': 'READY from HOMING.',
        '33': 'READY from MOVING.',
        '34': 'READY from DISABLE.',
        '36': 'READY T from READY.',
        '37': 'READY T from TRACKING.',
        '38': 'READY T from DISABLE T.',
        '3C': 'DISABLE from READY.',
        '3D': 'DISABLE from MOVING.',
        '3E': 'DISABLE from TRACKING.',
        '3F': 'DISABLE from READY T.',
        '46': 'TRACKING from READY T.',
        '47': 'TRACKING from TRACKING.'
    }

    MAX_RUN = 37000  # 35000 #empirically measured
    DEV = 1  # hardcoded here to the first device
    VERBOSE = False
    MOVEMENT_SLEEP_TIME = 0.05

    def __init__(self, com_port: str, velocity: float):
        self.driver = CommandInterfaceConexCC.ConexCC()
        ret = self.driver.OpenInstrument(com_port)
        if ret != 0:
            raise CCMotorCommunicationError(
                f"Error opening instrument at port: {com_port}")

        logger.info('ConexCC: Successfully connected to %s', com_port)
        self.velocity = velocity
        self.set_homing_velocity(velocity)

        self.min_limit: Optional[float] = None
        self.max_limit: Optional[float] = None
        self.get_limits()

        logger.debug('Current Position = %.3f mm', self.cur_pos_mm)

    def get_limits(self) -> Tuple[float, float]:
        """ Gets the minimum and maximum positions of the controller.
        Save these values to min_limit and max_limit."""
        res, resp, err_str = self.driver.SL_Get(self.DEV, 0, '')
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Negative SW Limit: result={res}, response={resp:.2f}, errString="{err_str}"')

        logger.debug('Negative SW Limit = %.1f nm', resp)
        self.min_limit = resp

        res, resp, err_str = self.driver.SR_Get(self.DEV, 0, '')
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Oops: Positive SW Limit: result={res},response={resp:.2f},errString="{err_str}"')
        logger.debug('Positive SW Limit = %.1f nm', resp)
        self.max_limit = resp

        return (self.min_limit, self.max_limit)

    def set_state(self, state: Literal[0, 1]) -> None:
        """ Send a request to set the state.
        State = 0 -> disable.
        State = 1 -> enable.
        """
        logger.debug('Setting state to %d', state)
        res, err_str = self.driver.MM_Set(self.DEV, state, "")
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Set state to {state}: result={res}, errString="{err_str}".')

    def set_disable(self):
        """ Disables the motor. """
        return self.set_state(0)

    def set_enable(self):
        """ Enables the motor. """
        return self.set_state(1)

    def set_homing_velocity(self, velocity: float) -> None:
        """ Sets the homing velocity. if velocity > MAX_VELOCITY then sets to MAX_VELOCITY """
        if velocity > self.MAX_VELOCITY:
            velocity = self.MAX_VELOCITY
        res, err_str = self.driver.OH_Set(self.DEV, velocity, '')
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Homing velocity: result={res}, errString="{err_str}".')

    def init_position_async(self) -> None:
        """ Sends a command to initialize the stage position to 0. Don't wait until done """
        res, err_str = self.driver.OR(self.DEV, '')
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Find Home: result={res},errString="{err_str}"')

    def init_position_sync(self, timeout: int = 30, n_retry: int = 3) -> None:
        """ Run init_position_async and wait until the stage is ready again.
        If the stage is not ready after timeout time, it raises a CCMotorTimeoutError or retries if n_retry>0.
        """
        self.init_position_async()
        time_start = time.time()
        done = False
        while not done:
            if time.time() - time_start > timeout:
                if n_retry > 0:
                    self.init_position_sync(timeout=timeout, n_retry=n_retry-1)
                    return
                raise CCMotorTimeoutError(timeout=timeout)
            sleep(self.MOVEMENT_SLEEP_TIME)
            done = self.is_ready

    def init_position_and_come_back(self):
        """ Reinitialize the position and comes back to current position. Waits until completed. """
        old_pos = self.cur_pos
        self.init_position_sync()
        self.move_absolute_sync(old_pos)

    def move_relative_async(self, distance_um: float) -> None:
        ''' Moves by the given distance. The distance units is um. '''
        cur_pos = self.cur_pos
        if cur_pos + distance_um > self.MAX_RUN:
            raise CCMotorRangeExceededError(
                pos=cur_pos + distance_um, max_pos=self.MAX_RUN)

        if not self.is_ready:
            raise CCMotorStateError("Stage not ready: " + self.state)

        res, err_str = self.driver.PR_Set(self.DEV, 1e-3*distance_um, '')
        if res != 0 or err_str != '':
            raise ValueError(f"Move went wrong: {err_str}")

        logger.debug('Moving relative by %.3f um', distance_um)

    def move_relative_sync(self, distance_um: float, timeout: int = 30):
        ''' Moves by the given distance. Waits until done. The distance units is um.
        If the stage is not ready after timeout time, it raises a CCMotorTimeoutError.
        It does not retry as the final position by relative moving is not well defined.
        '''
        self.move_relative_async(distance_um)
        time_start = time.time()
        done = False
        while not done:
            if time.time() - time_start > timeout:
                raise CCMotorTimeoutError(timeout=timeout)
            sleep(self.MOVEMENT_SLEEP_TIME)
            done = self.is_ready
        # checks the movement is completely done (for fine movement endings can be the case)

    def move_absolute_async(self, new_pos: float):
        ''' Moves to the given distance. The distance units is um. '''

        if new_pos > self.MAX_RUN:
            raise CCMotorRangeExceededError(pos=new_pos, max_pos=self.MAX_RUN)

        if not self.is_ready:
            raise CCMotorStateError(
                f"Stage not ready. Current state is : {self.state}")

        res, err_str = self.driver.PA_Set(self.DEV, 1e-3*new_pos, '')
        if res != 0 or err_str != '':
            raise ValueError("Move went wrong: " + err_str)
        logger.debug('Moving to position %.3f mm', new_pos)

    def move_absolute_sync(self, new_pos: float, timeout: int = 30, n_retry: int = 3):
        ''' Moves by the given distance. Waits until done. The distance units is um.
        If the stage is not ready after timeout time,
        it raises a CCMotorTimeoutError or retries if n_retry>0.
        '''

        self.move_absolute_async(new_pos)
        time_start = time.time()
        done = False
        while not done:
            if time.time() - time_start > timeout:
                if n_retry > 0:
                    self.set_enable()
                    self.init_position_sync()
                    self.move_absolute_sync(
                        new_pos, timeout=timeout, n_retry=n_retry-1)
                    return
                raise CCMotorTimeoutError(timeout=timeout)
            sleep(self.MOVEMENT_SLEEP_TIME)
            done = self.state in self.READY_STATES

    @property
    def possible_states(self) -> Dict[str, str]:
        """ Returns a dictionary of possible states.
        Docs: https://www.newport.com/mam/celum/celum_assets/resources/CONEX-CC_-_Controller_Documentation.pdf#page=54
        """
        return self.POSSIBLE_STATES

    @property
    def cur_pos_mm(self) -> float:
        """Gets the current position in mm"""
        err_str = ''
        resp = 0
        res, resp, err_str = self.driver.TP(self.DEV, 0, '')
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Current Position: result={res}, response={resp:.2f}, errString="{err_str}"')
        return resp

    @property
    def cur_pos(self) -> float:
        """ Gets the current position in um"""
        return self.cur_pos_mm*1e3

    @property
    def velocity(self) -> float:
        """ Gets the velocity"""
        res, resp, err_str = self.driver.VA_Get(self.DEV, 0, "")
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Oops: Current Velocity: result={res}, response={resp:.2f}, errString="{err_str}"')
        return resp

    @velocity.setter
    def velocity(self, speed: int):
        if speed > self.MAX_VELOCITY:
            speed = self.MAX_VELOCITY
            logger.warning(
                'Cannot set velocity higher than %.1f. Velocity set to maximal value.', self.MAX_VELOCITY)
        res, err_str = self.driver.VA_Set(self.DEV, speed, '')
        if res != 0 or err_str != '':
            raise CCMotorCommunicationError(
                f'Set velocity: result={res},errString="{err_str}"')

        logger.debug(f'Velocity set to %.1f mm/s', speed)

    def get_state(self) -> StateError:
        """ Returns StateError structure (NamedTuple). It has state and error attributes. """
        # res, resp, resp2, err_str = self.driver.TS(self.DEV, resp, resp2, err_str)  # pylint: disable=unused-variable
        _, error, state, err_str = self.driver.TS(self.DEV, '', '', '')
        if len(err_str):
            raise CCMotorCommunicationError(
                f'Oops: Cannot get the state. Error: {err_str}')

        return StateError(state=state, error=error)

    @property
    def state(self) -> str:
        """ Returns only the state """
        return self.get_state().state

    @property
    def is_ready(self) -> bool:
        """ Checks if the state is in one of the ready states """
        return self.state in self.READY_STATES

    @property
    def error(self) -> str:
        """ Returns only the error """
        return self.get_state().error

    def close(self) -> None:
        """ Closes the connection to the motor. It does not stop the motor."""
        self.driver.CloseInstrument()
