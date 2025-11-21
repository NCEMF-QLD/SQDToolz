"""
This is a driver for the Stahl power supplies
"""

import logging
import re
from collections import OrderedDict
from functools import partial
from typing import Any, Callable, Dict, Iterable, Optional

import numpy as np

import serial

from qcodes import Instrument

from qcodes.instrument import ChannelList, InstrumentChannel, VisaInstrument
from qcodes.utils.validators import Numbers

from qcodes.utils import validators as vals

logger = logging.getLogger()
import time

class SW_DCsmuBoxPort(InstrumentChannel):
    def __init__(self, parent, name, index):
        '''
        An instrument channel (port) in the DC SMU switch box.

        Arguments:
            portmap: `dict` with `str`:`SwitchPort` items
                Port names and state objects of the switch.
        '''
        super().__init__(parent, name)
        self._port = index
        self._parent = parent

        self.add_parameter(
            "state",
            get_cmd=lambda: self.get_state()
        )

    def get_state(self):
        tries = 100
        while (tries > 0):
            try:
                cur_val = int.from_bytes(self._parent.query([0xE0 | self._port]), byteorder='big')
                if (cur_val & 0x1F) == self._port:
                    ret_state = cur_val >> 5
                    if ret_state < len(self._parent._lestates):
                       return self._parent._lestates[ret_state]
            except:
                pass
            tries -= 1
        assert False, "Issue querying switch state?"

    @property
    def Position(self):
        return str(self.state())
    @Position.setter
    def Position(self, pos):
        state_val = self._parent._lestates.index(pos)
        msg = (state_val << 5) | self._port
        self._parent.write([msg])

    def get_all_switch_contacts(self):
        return self._lestates[:]

class SW_DCsmuBox(Instrument):
    """
    DC SMU Switch Box driver

    Args:
        name
        address: A serial port address
    """

    def __init__(self, name: str, address: str, ports = [f"Port{x}" for x in range(1,10)] + [f"Port{x}" for x in range(13,17)] + [f"Port{x}" for x in range(10,13)], **kwargs: Any):
        super().__init__(name, **kwargs)

        self.ser = serial.Serial(port=address, baudrate=9600, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=1)
        self._lestates = ["Psense", "Pforce", "Pground", "Pbnc", "Popen"]
        
        for m, cur_port in enumerate(ports):
            self.add_submodule(cur_port, SW_DCsmuBoxPort(self, cur_port, m))

    def get_idn(self):
        return 'DC SMU Switch Box'

    def write(self, cmd):
        self.ser.write(bytes(cmd))

    def query(self, cmd):
        self.ser.reset_input_buffer()
        self.write(cmd)
        ret_str = self.ser.read(1)
        return ret_str
    
    def set_ports_to_default(self, default_pos='Pground'):
        """Set all ports to the specified default position."""
        print(f"Setting all ports to default position: {default_pos}")
        for i in range(1, 17):
            port_number = f'Port{i}'
            port_obj = getattr(self, port_number)

            if port_obj.Position != default_pos:
                port_obj.Position = default_pos

            # pos = port_obj.Position
            # print(f'{port_number}.Position: {pos}')

    def print_port_positions(self):
        """Print the current position of all ports."""
        for i in range(1,17):

            port_number = f'Port{i}'

            port_obj = getattr(self, port_number)

            pos = port_obj.Position

            print(f'{port_number}.Position: {pos}')  




if __name__ == '__main__':
    test = SW_DCsmuBox('bob', '/dev/ttyUSB0')   #VISA Address for COM3 is ASRL3
    x = test.Port1.Position
    test.Port2.Position = 'Pforce'
    a=0