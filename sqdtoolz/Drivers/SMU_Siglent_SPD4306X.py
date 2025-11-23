from typing import Iterable, Optional, Union
from qcodes import Instrument, InstrumentChannel, ChannelList, validators as vals
from qcodes.instrument.visa import VisaInstrument

class SiglentSPD4306Channel(InstrumentChannel):
    """
    One channel of the SPD4306X source.
    Uses SCPI over SOCKET/TCPIP.
    """

    def __init__(self, parent: Instrument, name: str, ch: int):
        super().__init__(parent, name)
        self.ch = ch  # channel number 1–4
        
        # Channels have different max source voltages and current (see front pannel)
        if ch == 1:
            v_max, i_max = 15.0, 1.5
        elif ch in (2, 3):
            v_max, i_max = 30.0, 6.0
        elif ch == 4:
            v_max, i_max = 15.0, 1.0
        else:
            raise ValueError(f"SPD4306X only has channels 1-4, got {ch!r}")

        # Set voltage/current
        self.add_parameter(
            name="voltage",
            label=f"CH{ch} Voltage set",
            unit="V",
            set_cmd=f"SOUR:VOLT CH{ch},{{:.6f}}",
            get_cmd=f"SOUR:VOLT:SET? CH{ch}",
            vals=vals.Numbers(0, v_max),  # adjust per-channel limits if you want
            get_parser=float,
            step = 0.01
        )

        self.add_parameter(
            name="current",
            label=f"CH{ch} Current set",
            unit="A",
            set_cmd=f"SOUR:CURR CH{ch},{{:.6f}}",
            get_cmd=f"SOUR:CURR:SET? CH{ch}",
            vals=vals.Numbers(0, i_max),
            get_parser=float,
            step = 0.01
        )

        # Measured voltage/current
        self.add_parameter(
            name="voltage_measure",
            label=f"CH{ch} Voltage Meas",
            unit="V",
            get_cmd=f"MEAS:VOLT? CH{ch}",
            get_parser=float,
        )

        self.add_parameter(
            name="current_measure",
            label=f"CH{ch} Current Meas",
            unit="A",
            get_cmd=f"MEAS:CURR? CH{ch}",
            get_parser=float,
        )
        
        self.add_parameter(
            name="output",
            label=f"CH{ch} Output",
            set_cmd=f"OUTP CH{ch},{{}}",
            get_cmd=f"OUTP? CH{ch}",
            # Keys: what you use in Python
            # Values: what the instrument expects/returns
            val_mapping={
                False: "0",
                True:  "1",
            },
        )

    @property
    def Output(self):
        return self.output()          # already a bool

    @Output.setter
    def Output(self, val):
        # Accept True/False, 1/0, "on"/"off"
        if isinstance(val, str):
            v = val.strip().lower()
            if v in ("on", "1", "true"):
                val = True
            elif v in ("off", "0", "false"):
                val = False
            else:
                raise ValueError(f"Invalid Output value {val!r}")
        self.output(bool(val))

    @property
    def Voltage(self):
        return self.voltage()
    @Voltage.setter
    def Voltage(self, val):
        self.voltage.set(val)

    @property
    def Current(self):
        return self.current()
    @Current.setter
    def Current(self, val):
        self.current.set(val)
    
    @property
    def SenseVoltage(self):
        return self.voltage_measure()

    @property
    def SenseCurrent(self):
        return self.current_measure()

    @property
    def Output(self):
        return self.output()
    @Output.setter
    def Output(self, val):
        self.output(val)
    
    @property
    def ComplianceCurrent(self):
        return self.Current
    @ComplianceCurrent.setter
    def ComplianceCurrent(self, val):
        self.Current = val
    
    @property
    def ComplianceVoltage(self):
        return self.Voltage
    @ComplianceVoltage.setter
    def ComplianceVoltage(self, val):
        self.Voltage = val
    
    @property
    def Mode(self):
        cv = self._get_status()[1]
        if cv:
            return 'SrcV_MeasI'
        else:
            return 'SrcI_MeasV'
    @Mode.setter
    def Mode(self, val):
        pass    #Cannot set the mode on this one...

    @property
    def SupportsSweeping(self):
        return False
    
    @property
    def RampRateVoltage(self):
        return self.voltage.step/self.voltage.inter_delay
    @RampRateVoltage.setter
    def RampRateVoltage(self, val):
        ramp_rate = val
        if ramp_rate < 0.01:
            self.voltage.step = 0.001
        elif ramp_rate < 0.1:
            self.voltage.step = 0.010
        elif ramp_rate < 1.0:
            self.voltage.step = 0.100
        else:
            self.voltage.step = 1.0
        self.voltage.inter_delay = self.voltage.step / ramp_rate

    @property
    def RampRateCurrent(self):
        return self.current.step/self.current.inter_delay
    @RampRateCurrent.setter
    def RampRateCurrent(self, val):
        ramp_rate = val
        if ramp_rate < 0.01:
            self.current.step = 0.001
        elif ramp_rate < 0.1:
            self.current.step = 0.010
        elif ramp_rate < 1.0:
            self.current.step = 0.100
        else:
            self.current.step = 1.0
        self.current.inter_delay = self.current.step / ramp_rate

    @property
    def ProbeType(self):
        return 'TwoWire'
    @ProbeType.setter
    def ProbeType(self, val):
        pass    #Can't set this one...

    def _get_status(self):
        src_output = self.write(f'OUTP? CH{self.ch}')
        status = self.ask(f"MEAS:RUN:MODE? CH{self.ch}")
        if src_output == 1:
            output = True
        else:
            output = False
        if status == 'CV' :
            cv = True # Power supply is in Constant Voltage mode
        else:
            cv = False # Power supply is in Constant Current mode
        return output, cv


class SiglentSPD4306(VisaInstrument):
    """Qcodes driver for controlling 4 channel SiglentSPD4306
       Comms through LAN by default.The driver is written to use this as a power source.
       It can also be used as a SMU with appropriate modification to the driver. See user manual.
    """
    def __init__(
        self,
        name: str,
        address: str,
        channels: Optional[Iterable[int]] = None,
        **kwargs,
    ):
        # VISA instrument, using \n termination
        super().__init__(name, address, terminator="\n", **kwargs)

        # Ensure VISA terminations explicit
        try:
            self.visa_handle.read_termination = "\n"
            self.visa_handle.write_termination = "\n"
        except Exception:
            pass

        # identify (also forces link ready)
        _ = self.IDN()

        # Channel configuration
        if channels is None:
            channels = [1, 2, 3, 4]  # SPD4306X has 4 channels

        ch_objs = []
        for ch in channels:
            chn = SiglentSPD4306Channel(self, f"ch{ch}", ch)
            self.add_submodule(f"ch{ch}", chn)
            ch_objs.append(chn)

        self.channels = ChannelList(self, "channels", SiglentSPD4306Channel, ch_objs)
        self.add_submodule("channels", self.channels)

        # # Other system utilities
        # self.add_parameter(
        #     "beep",
        #     set_cmd="SYST:BEEP {}",
        #     get_cmd="SYST:BEEP?",
        #     val_mapping={"off": "OFF", "on": "ON", 0: "OFF", 1: "ON"},
        # )

        self.add_parameter(
            "error_queue",
            get_cmd="SYST:ERR?",
            docstring="Query next error in the queue.",
        )

        self.connect_message()

    # ---- Helper functions ----
    def IDN(self) -> str:
        """Return the identification string."""
        return self.ask("*IDN?").strip()

    def reset(self) -> None:
        """SCPI *RST (use with care)."""
        self.write("*RST")

    def clear_status(self) -> None:
        """SCPI *CLS."""
        self.write("*CLS")

    def output_all(self, state: Union[bool, str, int]) -> None:
        """
        Turn all configured channels True or False by iterating per channel.
        """
        for ch in self.channels:
            ch.output(state)
    