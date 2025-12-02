import time
import logging
import numpy as np
import pandas as pd

import sqdtoolz

from qcodes import VisaInstrument, validators as vals, InstrumentChannel
from qcodes.parameters import Parameter

log = logging.getLogger(__name__)

# class KeysightSA_N9323C_Channel(InstrumentChannel):
#     """
#     A “channel” or submodule of the instrument (if applicable).
#     For example: for a multi-channel source, digitizer, etc.
#     """

#     def __init__(self, parent, name, channel_id, **kwargs):
#         super().__init__(parent, name, **kwargs)
#         self._channel_id = channel_id

#         # Example parameter: channel enable (on/off)
#         self.add_parameter(
#             'enable',
#             label=f'Channel {channel_id} enable',
#             get_cmd=lambda: self._parent._query(f"CHAN{channel_id}:ENABLE?"),
#             set_cmd=lambda x: self._parent._write(f"CHAN{channel_id}:ENABLE {int(x)}"),
#             vals=vals.Ints(0, 1),
#             docstring="Enable (1) or disable (0) this channel."
#         )

 

class Keysight_N9323C(VisaInstrument):
    """
    QCoDeS driver for KeysightSA_N9323C.
    """

    def __init__(self, name: str, address: str, timeout: float = 10, **kwargs):
        """
        Args:
            name: name of the instrument instance in QCoDeS station
            address: VISA resource string, e.g. "TCPIP0::192.168.0.123::INSTR" or GPIB, USB, etc.
            timeout: VISA timeout in seconds
            **kwargs: any additional args passed to VisaInstrument
        """
        super().__init__(name, address, timeout=timeout, **kwargs)

        # optionally: set terminator, if needed
        self.write_termination = '\n'
        self.read_termination = '\n'
        
        
        

        # Create channels/submodules if needed
        # For example, if there are 2 channels:
        # self.add_submodule("ch1", KeysightSA_N9323C_Channel(self, "ch1", channel_id=1))
        # self.add_submodule("ch2", KeysightSA_N9323C_Channel(self, "ch2", channel_id=2))

        # Add global parameters (not per-channel)
        # set the center frequency
        self.add_parameter(
            name='sense_frequency_centre', 
            label = 'Sense Frequency Centre', 
            unit = 'Hz',
            get_cmd= f"SENSe:FREQuency:CENTer?",
            get_parser=float,
            set_cmd = f"SENSe:FREQuency:CENTer {{}}",
            vals=vals.Numbers(),
            docstring="Set or get the instrument centre frequency."
        )
        # set the frequency span
        self.add_parameter(
            name='sense_frequency_span', 
            label = 'Sense Frequency Span', 
            unit = 'Hz',
            get_cmd= f'SENSe:FREQuency:SPAN?',
            get_parser=float,
            set_cmd = f'SENSe:FREQuency:SPAN {{}}',
            vals=vals.Numbers(),
            docstring="Set or get the instrument frequency span."
        )
        # set the start frequency
        self.add_parameter(
            name='sense_frequency_start', 
            label = 'Sense Frequency start', 
            unit = 'Hz',
            get_cmd= f'FREQuency:STARt?',
            get_parser=float,
            set_cmd = f'FREQuency:STARt {{}}',
            vals=vals.Numbers(),
            docstring="Set or get the instrument start frequency."
        )
        # set the stop frequency
        self.add_parameter(
            name='sense_frequency_stop', 
            label = 'Sense Frequency Stop', 
            unit = 'Hz',
            get_cmd= f'FREQuency:STOP?',
            get_parser=float,
            set_cmd = f'FREQuency:STOP {{}}',
            vals=vals.Numbers(),
            docstring="Set or get the instrument stop frequency."
        )
        # set the resolution bandwidth
        self.add_parameter(
            name='sense_resolution_bandwidth', 
            label = 'Sense Resolution Bandwidth', 
            unit = 'Hz',
            get_cmd= f'SENSe:BANDwidth:RESolution?',
            get_parser=float,
            set_cmd = f'SENSe:BANDwidth:RESolution {{}}',
            vals=vals.Numbers(min_value=10, max_value=3e6),
            docstring="Set or get the instrument resolution bandwidth."
        )
        # set the sweep time (the number of sweep points is fixed, 
        # increasing the sweep time will increase the integration time of the RBW filter)
        self.add_parameter(
            name='sense_sweep_time', 
            label = 'Sense Sweep Time', 
            unit = 'Second',
            get_cmd= f'SENSe:SWEep:TIME?',
            get_parser=float,
            set_cmd = f'SENSe:SWEep:TIME {{}}',
            vals=vals.Numbers(),
            docstring="Set or get the instrument sweep time."
        )
        self.add_parameter(
            name='sense_sweep_points', 
            label = 'Sense Sweep Points: 461', 
            unit = 'a.u.',
            # get_cmd= f'SENSe:SWEep:POINts?',
            get_parser=int,
            # set_cmd = f'SENSe:SWEep:POINts {{}}',
            # vals=vals.Numbers(),
            docstring="Get the instrument sweep points."
        )
        # turns on/off auto sweep time state
        ###################################
        ############# does not work!!! revisit
        self.add_parameter(
            name='sense_auto_sweep_enable', 
            label = 'Sense Auto_sweep Enable', 
            # unit = 'Hz',
            get_cmd= f'SENSe:SWEep:TIME:AUTO?',
            get_parser= str.strip, #lambda x: bool(int(x)),
            set_cmd = f'SENSe:SWEep:TIME:AUTO {{}}',
            # Keys: what you use in Python
            # Values: what the instrument expects/returns
            val_mapping={
                False: "0",
                True:  "1",},
            docstring="enable or disable the instrument auto sweep."
        )

        # to enable average
        self.add_parameter(
            name='average_enable',
            docstring = 'Enables average',
            get_parser = str.strip,
            get_cmd = ':AVERage:TRACe1:STATe?', 
            set_cmd = ':AVERage:TRACe1:STATe {}',
            val_mapping = {True: 1, False: 0}
            )
        
        # to set the average count
        self.add_parameter(
            name='average_count', 
            label = 'Number of averages',
            get_cmd=':AVERage:TRACe1:COUNt?',
            get_parser=int,
            set_cmd = ':AVERage:TRACe1:COUNt {}',
            vals=vals.Numbers()
            )
        
        # to query and set the average type
        self.add_parameter(
            name='average_type', 
            label = 'Type of average',
            get_cmd=':AVERage:TYPE?',
            get_parser=int,
            set_cmd = ':AVERage:TYPE {}',
            vals=vals.Enum('LOGPower', 'VOLTage', 'POWer'),    #POWer is linear, meaning average first then take log, POW is the reverse...
            initial_value='POWer'
            )
        
        # to restart the average
        self.add_parameter(
        name='average_restart', 
        label = 'Restart the average', 
        unit = 'a.u.',
        set_cmd = ':AVERage:TRACe1:{}',
        vals=vals.Enum('CLEar')
        )

        

        






    @property
    def FrequencyCentre(self):        
        return self.sense_frequency_centre()
    @FrequencyCentre.setter
    def FrequencyCentre(self, vals):
        self.sense_frequency_centre(vals)

    @property
    def FrequencySpan(self):        
        return self.sense_frequency_span()
    @FrequencySpan.setter
    def FrequencySpan(self, vals):
        self.sense_frequency_span(vals)

    @property
    def FrequencyStart(self):     
        return self.sense_frequency_start()
    @FrequencyStart.setter
    def FrequencyStart(self, vals):
        self.sense_frequency_start(vals)

    @property
    def FrequencyEnd(self):        
        return self.sense_frequency_stop()
    @FrequencyEnd.setter
    def FrequencyEnd(self, vals):
        self.sense_frequency_stop(vals)
    
    @property
    def Bandwidth(self):        
        return self.sense_resolution_bandwidth()
    @Bandwidth.setter
    def Bandwidth(self, vals):
        self.sense_resolution_bandwidth(vals)

    @property
    def AutoSweepEnable(self):        
        return self.sense_auto_sweep_enable()
    @AutoSweepEnable.setter
    def AutoSweepEnable(self, vals):
        # Accept True/False, 1/0, "on"/"off"
        if isinstance(vals, str):
            v = vals.strip().lower()
            if v in ("on", "1", "true"):
                vals = True
            elif v in ("off", "0", "false"):
                vals = False
            else:
                raise ValueError(f"Invalid Output value {vals!r}")
        self.sense_auto_sweep_enable(bool(vals))

    @property
    # Sweep time is called integration time in HAL of sqdtoolz
    def IntegrationTime(self):        
        return self.sense_sweep_time()
    @IntegrationTime.setter
    def IntegrationTime(self, vals):
        self.write('SENSe:SWEep:TIME:AUTO 0')  # disable auto sweep time first
        self.sense_sweep_time(vals)

    @property
    def SweepPoints(self):        
        return 461
    @SweepPoints.setter
    def SweepPoints(self, vals):
        raise NotImplementedError("Sweep points is fixed to 461 in this model.")


    @property
    def AveragesEnable(self):        
        return self.average_enable()
    @AveragesEnable.setter
    def AveragesEnable(self, vals):
        # Accept True/False, 1/0, "on"/"off"
        if isinstance(vals, str):
            v = vals.strip().lower()
            if v in ("on", "1", "true"):
                vals = True
            elif v in ("off", "0", "false"):
                vals = False
            else:
                raise ValueError(f"Invalid Output value {vals!r}")
        self.average_enable(bool(vals))


    @property
    def AveragesNum(self):
        return self.average_count()
    @AveragesNum.setter
    def AveragesNum(self, vals):
        self.average_count(vals)

    @property
    def AverageType(self):
        return self.average_type()
    @AverageType.setter
    def AverageType(self,vals):
        self.average_type(vals)

    def AverageRestart(self):
        return self.average_restart.set()

    
 
    def get_data(self, **kwargs):
        ############# Number of points in frequency sweep is fixed to be 461 ###############
        ############# in this spectrum analyser model Keysight N9323C        ###############
        # if no data stitching
        # self.write('INIT:CONT OFF') # trigger a single sweep
        # self.ask('*CLS;INIT:IMM;*OPC?') # clears the analyser; trigger a sweep and delay for sweep to complete; Operation Complete Query 
        #    # (this query stops any new commands from being processed until the current processing is cmplete); if *CLS has bugs, maybe *RST
        # This query command returns the current displayed ascii data, not binary data
        # wfm_data = self.visa_handle.query_ascii_values('trace:data? trace1', separator= ',', converter='f')
        # wfm_x = np.linspace(self.sense_frequency_start(), self.sense_frequency_stop(), 461)
        ############# data stitching implemented below ###############
        ############# for span > 500 MHz, since max span with 461 points is 500 MHz ###############
         ############# each segment has 461 points ###############  
        # if data stitching is needed, 500 MHz span per segment with the 461 points
        span = self.sense_frequency_span()
        start_freq = self.sense_frequency_start()
        stop_freq = self.sense_frequency_stop()

        average_state = self.AveragesEnable
        average_count = self.AveragesNum


        print(f"Start frequency: {start_freq} Hz")
        print(f"Stop frequency: {stop_freq} Hz")
        print(f"average: {average_count} counts, enabled: {average_state}")

        num_segments = int(np.ceil(span / 5e8))
        freqs_per_segment = []
        for seg in range(num_segments):
            seg_start = start_freq + seg * 5e8
            seg_stop = min(seg_start + 5e8, stop_freq)
            freqs = np.linspace(seg_start, seg_stop, 461)
            freqs_per_segment.append(freqs)
        wfm_x = np.concatenate(freqs_per_segment)
        wfm_data = []
        for seg in range(num_segments):
            seg_start = start_freq + seg * 5e8
            seg_stop = min(seg_start + 5e8, stop_freq)
            self.write(f'FREQ:STAR {seg_start}')
            self.write(f'FREQ:STOP {seg_stop}')
            
            self.write('INIT:CONT OFF')# trigger a single sweep
            self.ask('*CLS;INIT:IMM;*OPC?') # clears the analyser; trigger a sweep and delay for sweep to complete; Operation Complete Query 
            # (this query stops any new commands from being processed until the current processing is cmplete); if *CLS has bugs, maybe *RST
            self.write(f':AVERage:TRACe1:STATe {int(average_state)}')  # enable average
            self.write(f':AVERage:TRACe1:COUNt {average_count}')  # set average count
            self.write(':AVERage:TRACe1:CLEar')  # restart average  
            # wait for the averaging to complete    
            seg_data = self.visa_handle.query_ascii_values('trace:data? trace1', separator= ',', converter='f') # This query command returns the current displayed ascii data, not binary data
            wfm_data.extend(seg_data)

        # restore the original start and stop frequency
        self.write(f'FREQ:STAR {wfm_x[0]}')  
        self.write(f'FREQ:STOP {wfm_x[-1]}')
        self.write('INIT:CONT 1')# set back to continuous sweep





    
        
        ret_data = {
            'parameters' : ['Frequency'],
            'data' : {},
            'parameter_values' : {}
            }
        
        ret_data['data'][f'Power_dBm'] = np.array(wfm_data)
        ret_data['parameter_values']['Frequency'] = np.array(wfm_x)

        leProc = kwargs.get('data_processor', None)
        if leProc is not None:
            leProc.push_data(ret_data)
            return {'data': leProc.get_all_data()}
        return {'data': ret_data}
        # return ret_data




if __name__=='__main__':
    inst_obj = Keysight_N9323C('test', address='TCPIP::10.200.1.143::INSTR')