import time
from turtle import mode

from qcodes import Instrument, InstrumentChannel, VisaInstrument, validators as vals
import numpy as np

class SMU_B2901B(VisaInstrument):
    """This class represents and controls a Keysight B2901B SMU. For operating
    details of this instrument, refer to Keysight document B2910-90030, titled
    "Keysight B2900 SCPI Command Reference". Expanded with fast sweep/list mode."""

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.description = "Keysight B2901 SMU"
        self.expectedMfr = "Keysight Technologies"
        self.expectedModel = "B2901B"
        self.VID = 0x0957
        self.PID = 0x8b18
        #instrument-specific additional setup
        self.write("*ESE 1")    #enable summary of bit 0, Event Status register, to enable *OPC monitoring
        self.write("*SRE 32")   #enable summary of bit 5, Status Byte, to enable *OPC monitoring

        #Set to auto-ranging
        self.write(':RANG:AUTO:VOLT ON')
        self.write(':RANG:AUTO:CURR ON')
        #Setup compliance checks
        self.write(':OUTP:PROT OFF')
        self.write(':CALC:LIM:FUNC COMP')
        self.write(':CALC:LIM:COMP:FAIL OUT')
        self.write(":CALC:LIM:STAT 0")
        # self.write(":CALC:LIM:STAT?") WHY DOES self.ask(":SENS:CURR:PROT:TRIP?") NOT WORK?!?!?!?
        #TODO: Currently it sends out nan for compliance hit; but that isn't realiable. Figure out how to get TRIP working so that it returns a nice saturated compliance value instead...

        self.add_parameter('volt_force',
                           label='Output Voltage',
                           get_cmd='SOUR:VOLT?',
                           set_cmd='SOUR:VOLT {}',
                           vals=vals.Numbers(-210.0, 210.0),
                           get_parser=float,
                           inter_delay=0.05,
                           step=0.001)

        self.add_parameter('current_force',
                           label='Output Current',
                           get_cmd='SOUR:CURR?',
                           set_cmd='SOUR:CURR {}',
                           vals=vals.Numbers(-3.0, 3.0),
                           get_parser=float,
                           inter_delay=0.05,
                           step=0.001)

        self.add_parameter('current_compliance',
                           label='Compliance Current',
                           get_cmd=':SENS:CURR:PROT?',
                           set_cmd=':SENS:CURR:PROT {}',
                           vals=vals.Numbers(-3.0, 3.0),
                           get_parser=float)

        self.add_parameter('voltage_compliance',
                           label='Compliance Current',
                           get_cmd=':SENS:VOLT:PROT?',
                           set_cmd=':SENS:VOLT:PROT {}',
                           vals=vals.Numbers(-210.0, 210.0),
                           get_parser=float)

        self.add_parameter('output',
                            get_cmd=':OUTP?',
                            set_cmd=':OUTP {}',
                            set_parser=int,
                            val_mapping={True:  1, False : 0})

        self.add_parameter('mode',
                            get_cmd=lambda : self.ask(':FUNC:MODE?').strip(),
                            set_cmd=':FUNC:MODE {}',
                            val_mapping={'SrcV_MeasI' : 'VOLT', 'SrcI_MeasV' : 'CURR'})
        
        self.add_parameter('voltage_ramp_rate', unit='V/s',
                            label="Output voltage ramp-rate",
                            initial_value=2.5e-3/0.05,
                            vals=vals.Numbers(0.001, 100),
                            get_cmd=lambda : self.volt_force.step/self.volt_force.inter_delay,
                            set_cmd=self._set_ramp_rate_volt)

        self.add_parameter('current_ramp_rate', unit='A/s',
                            label="Output current ramp-rate",
                            initial_value=0.001,
                            vals=vals.Numbers(0.001, 100),
                            get_cmd=lambda : self.current_force.step/self.current_force.inter_delay,
                            set_cmd=self._set_ramp_rate_current)

        self.add_parameter('current_measure', unit='A',
                            label="Current Measure",
                            get_parser=float,
                            get_cmd=":MEAS:CURR?")

        self.add_parameter('volt_measure', unit='V',
                            label="Voltage Measure",
                            get_parser=float,
                            get_cmd=":MEAS:VOLT?")

        self.add_parameter('meas_probe_type',
                            get_cmd=lambda: self.ask(':SENS:REM?').strip(),
                            set_cmd=':SENS:REM {}',
                            val_mapping = {'TwoWire' : '0', 'FourWire' : '1'})

        self._last_user_output_state = self.Output
        
        self.add_parameter('sweep_v_start',
                            label='Voltage Sweep Start',
                            get_cmd=':SOUR:VOLT:STAR?',
                            set_cmd=':SOUR:VOLT:STAR {}',
                            vals=vals.Numbers(-210.0, 210.0),
                            get_parser=float)
        
        self.add_parameter('sweep_v_end',
                            label='Voltage Sweep Stop',
                            get_cmd=':SOUR:VOLT:STOP?',
                            set_cmd=':SOUR:VOLT:STOP {}',
                            vals=vals.Numbers(-210.0, 210.0),
                            get_parser=float)
        
        self.add_parameter('sweep_v_points',
                            label='Voltage Sweep Points',
                            get_cmd=':SOUR:VOLT:POIN?',
                            set_cmd=':SOUR:VOLT:POIN {}',
                            vals=vals.Numbers(2, 1000),
                            get_parser=int)
        
        self.add_parameter('sweep_i_start',
                            label='Current Sweep Start',
                            get_cmd=':SOUR:CURR:STAR?',
                            set_cmd=':SOUR:CURR:STAR {}',
                            vals=vals.Numbers(-1.0, 1.0),
                            get_parser=float)
        
        self.add_parameter('sweep_i_end',
                            label='Current Sweep Stop',
                            get_cmd=':SOUR:CURR:STOP?',
                            set_cmd=':SOUR:CURR:STOP {}',
                            vals=vals.Numbers(-1.0, 1.0),
                            get_parser=float)
        
        self.add_parameter('sweep_i_points',
                            label='Current Sweep Points',
                            get_cmd=':SOUR:CURR:POIN?',
                            set_cmd=':SOUR:CURR:POIN {}',
                            vals=vals.Numbers(2, 1000),
                            get_parser=int)

        self.add_parameter('sweep_v_mode',
                            label='Voltage Sweep Mode',
                            get_cmd=lambda: self.ask(':SOUR:VOLT:MODE?').strip(),
                            set_cmd=':SOUR:VOLT:MODE {}',)

        self.add_parameter('sweep_i_mode',
                            label='Current Sweep Mode',
                            get_cmd=lambda: self.ask(':SOUR:CURR:MODE?').strip(),
                            set_cmd=':SOUR:CURR:MODE {}',)
        
        self.add_parameter('trig_source_delay',
                            label='Trigger Source Delay',
                            unit='s',
                            get_cmd=':TRIG:TRAN:DEL?',
                            set_cmd=':TRIG:TRAN:DEL {}',
                            vals=vals.Numbers(0, 10),
                            get_parser=float)
        
        self.add_parameter('trig_acq_delay',
                            label='Trigger Acquisition Delay',
                            unit='s',
                            get_cmd=':TRIG:ACQ:DEL?',
                            set_cmd=':TRIG:ACQ:DEL {}',
                            vals=vals.Numbers(0, 10),
                            get_parser=float)
        

        
        self._sweep_direction = 'UP'
        self._sweep_dir_mode = 'SING'
        self._sweep_list = []
        self._dwell_time = 10E-3

    @property
    def Mode(self):
        return self.mode()
    @Mode.setter
    def Mode(self, mode):
        self.mode(mode)
        self.write(':OUTP:PROT ON')
        if mode == 'SrcV_MeasI':
            self.write(':SENS:FUNC CURR')
        else:
            self.write(':SENS:FUNC VOLT')

    @property
    def Output(self):
        return self.output()
    @Output.setter
    def Output(self, val):
        self._last_user_output_state = val
        self.write(':OUTP:PROT ON')
        self.output(val)

    @property
    def Voltage(self):
        return self.volt_force()
    @Voltage.setter
    def Voltage(self, val):
        # temp = self._last_user_output_state
        # self.Output = False
        self.volt_force(val)
        # self._last_user_output_state = temp
        # self.Output = self._last_user_output_state

    @property
    def Current(self):
        return self.current_force()
    @Current.setter
    def Current(self, val):
        #TODO: This is bad as it literally sets the output to zero - can the device be unlocked without turning output explicitly off?!
        # temp = self._last_user_output_state
        # self.Output = False
        self.current_force(val)
        # self._last_user_output_state = temp
        # self.Output = self._last_user_output_state

    @property
    def SenseVoltage(self):
        if self.Output != self._last_user_output_state: #i.e. it turned off due to compliance
            return np.nan
        return np.clip(self.volt_measure(), -210, 210)
   
    def is_tripped(self):
        return int(self.ask(":SYST:INT:TRIP?"))

    @property
    def SenseCurrent(self):
        if self.Output != self._last_user_output_state: #i.e. it turned off due to compliance
            return np.nan
        return self.current_measure()
    
    @property
    def ComplianceCurrent(self):
        return self.current_compliance()
    @ComplianceCurrent.setter
    def ComplianceCurrent(self, val):
        self.current_compliance(val)
    
    @property
    def ComplianceVoltage(self):
        return self.voltage_compliance()
    @ComplianceVoltage.setter
    def ComplianceVoltage(self, val):
        self.voltage_compliance(val)

    @property
    def RampRateVoltage(self):
        return self.voltage_ramp_rate()
    @RampRateVoltage.setter
    def RampRateVoltage(self, val):
        self.voltage_ramp_rate(val)

    @property
    def RampRateCurrent(self):
        return self.current_ramp_rate()
    @RampRateCurrent.setter
    def RampRateCurrent(self, val):
        self.current_ramp_rate(val)

    @property
    def SupportsSweeping(self):
        return True

    @property
    def SweepSampleTime(self):
        return self._get_aperture_time()
    @SweepSampleTime.setter
    def SweepSampleTime(self, smpl_time_seconds):
        self._set_aperture_time(smpl_time_seconds)
    
    @property
    def SweepSamplePoints(self):
        if self.mode() == 'SrcV_MeasI':
            return self.sweep_v_points()
        else:
            return self.sweep_i_points()

    @SweepSamplePoints.setter
    def SweepSamplePoints(self, val):
        if self.mode() == 'SrcV_MeasI':
            self.sweep_v_points(val)
        else:
            self.sweep_i_points(val)
    
    @property
    def SweepStartValue(self):
        if self.mode() == 'SrcV_MeasI':
            return self.sweep_v_start()
        else:
            return self.sweep_i_start()
    @SweepStartValue.setter
    def SweepStartValue(self, val):
        if self.mode() == 'SrcV_MeasI':
            self.sweep_v_start(val)
        else:
            self.sweep_i_start(val)

    @property
    def SweepEndValue(self):
        if self.mode() == 'SrcV_MeasI':
            return self.sweep_v_end()
        else:
            return self.sweep_i_end()
    @SweepEndValue.setter
    def SweepEndValue(self, val):
        if self.mode() == 'SrcV_MeasI':
            self.sweep_v_end(val)
        else:
            self.sweep_i_end(val)

    @property
    def ProbeType(self):
        return self.meas_probe_type()
    @ProbeType.setter
    def ProbeType(self, connection):
        assert connection == 'TwoWire' or connection == 'FourWire', "ProbeType must be FourWire or TwoWire"
        self.meas_probe_type(connection)

    @property
    def SweepMode(self):
        if self.mode() == 'SrcV_MeasI':
            return self.sweep_v_mode()
        else:
            return self.sweep_i_mode()
    @SweepMode.setter
    def SweepMode(self, val):
        assert val in ('SWE', 'LIST'), "Sweep mode must be SWE or LIST"
        if self.mode() == 'SrcV_MeasI':
            self.sweep_v_mode(val)
        else:
            self.sweep_i_mode(val)
        # print(f"DEBUG: Set sweep mode to {val}")
    
    @property
    def SweepRepeat(self):
        return self._get_sweep_dir_mode()
    @SweepRepeat.setter
    def SweepRepeat(self, val):
        assert val in ('SING', 'DOUB'), "Sweep direction mode must be SING or DOUB"
        self._set_sweep_dir_mode(val)

    @property
    def TriggerSourceDelay(self):
        return self.trig_source_delay()
    @TriggerSourceDelay.setter
    def TriggerSourceDelay(self, val):
        self.trig_source_delay(val)

    @property
    def TriggerAcquisitionDelay(self):
        return self.trig_acq_delay()    
    @TriggerAcquisitionDelay.setter
    def TriggerAcquisitionDelay(self, val):
        self.trig_acq_delay(val)

    @property
    def SweepDirection(self):
        return self._get_sweep_direction()
    @SweepDirection.setter
    def SweepDirection(self, val):
        assert val in ('Up', 'Down'), "Sweep direction must be Up or Down"
        self._set_sweep_direction(val)

    @property
    def SweepList(self):
        return self._get_sweep_list()
    @SweepList.setter
    def SweepList(self, val):
        if isinstance(val, (list, np.ndarray)):
            self._set_sweep_list(val)
        else:
            raise ValueError("SweepList must be a list or numpy array of numbers")

    @property
    def SampleApertureTime(self):
        return self._get_aperture_time()
    @SampleApertureTime.setter
    def SampleApertureTime(self, val):
        self._set_aperture_time(val)

    def _set_ramp_rate_volt(self, ramp_rate):
        if ramp_rate < 0.01:
            self.volt_force.step = 0.001
        elif ramp_rate < 0.1:
            self.volt_force.step = 0.010
        elif ramp_rate < 1.0:
            self.volt_force.step = 0.100
        else:
            self.volt_force.step = 1.0
        self.volt_force.inter_delay = self.volt_force.step / ramp_rate

    def _set_ramp_rate_current(self, ramp_rate):
        if ramp_rate < 0.01:
            self.current_force.step = 0.001
        elif ramp_rate < 0.1:
            self.current_force.step = 0.010
        elif ramp_rate < 1.0:
            self.current_force.step = 0.100
        else:
            self.current_force.step = 1.0
        self.current_force.inter_delay = self.current_force.step / ramp_rate

    def _active_sweep_parameters(self):
            if self.mode() == 'VOLT':
                return self.sweep_v_start, self.sweep_v_stop, self.sweep_v_points
            return self.sweep_i_start, self.sweep_i_stop, self.sweep_i_points
    
    def _set_sweep_mode(self, val):
        cur_mode = self.mode()
        if cur_mode in ('SrcV_MeasI', 'VOLT'):
            self.write(f':SOUR:VOLT:MODE {val}')
        elif cur_mode in ('SrcI_MeasV', 'CURR'):
            self.write(f':SOUR:CURR:MODE {val}')
        else:
            raise ValueError("Invalid mode for sweep")
        
    def _get_sweep_mode(self):
        cur_mode = self.mode()
        if cur_mode in ('SrcV_MeasI', 'VOLT'):
            return self.ask(':SOUR:VOLT:MODE?').strip()
        elif cur_mode in ('SrcI_MeasV', 'CURR'):
            return self.ask(':SOUR:CURR:MODE?').strip()
        else:
            raise ValueError("Invalid mode for sweep")
       
    def _set_sweep_direction(self, val):
        self._sweep_direction = val
        if self.SweepMode != 'SWE':
            raise ValueError("SweepDirection is only supported in SWE mode")
        self.write(f':SOUR:SWE:DIR {val.upper()}')

    def _get_sweep_direction(self):
        if self.SweepMode != 'SWE':
            raise ValueError("SweepDirection is only supported in SWE mode")
        return self.ask(':SOUR:SWE:DIR?').strip()
    
    def _set_sweep_dir_mode(self, val):
        if self.SweepMode == 'LIST':
            raise ValueError("STA parameter is not supported for LIST sweep mode. SweepRepeat cannot be set in LIST mode.")
        # self._sweep_dir_mode = val
        if self.SweepMode == 'SWE':
            self.write(f':SOUR:SWE:STA {val.upper()}')
        # print(f"DEBUG: Set sweep repeat mode to {val} for sweep mode {self.SweepMode}")

    def _get_sweep_dir_mode(self):
        if self.SweepMode == 'LIST':
            return 'SING'
        if self.SweepMode == 'SWE':
            return self.ask(':SOUR:SWE:STA?').strip()

    def _set_sweep_list(self, val):
        if isinstance(val, (list, np.ndarray)):
            self._sweep_list = ','.join(str(float(x)) for x in val)
            self.SweepStartValue = float(min(val))
            self.SweepEndValue = float(max(val))
            self.SweepSamplePoints = len(val)
            if self.Mode == 'SrcV_MeasI':
                self.write(f':SOUR:LIST:VOLT {self._sweep_list}')
            elif self.Mode == 'SrcI_MeasV':
                self.write(f':SOUR:LIST:CURR {self._sweep_list}')
        else:
            raise ValueError("SweepList must be a list or numpy array of numbers")
        
    def _get_sweep_list(self):
        if self.Mode == 'SrcV_MeasI':
            return self.ask(f':SOUR:LIST:VOLT?').split(',')
        elif self.Mode == 'SrcI_MeasV':
            return self.ask(f':SOUR:LIST:CURR?').split(',')
        else:
            raise ValueError("Invalid mode for sweep list")

    def _set_aperture_time(self, val):
        if self.Mode == 'SrcV_MeasI':
            self.write(f':SENS:CURR:APER {val}')
        else:
            self.write(f':SENS:VOLT:APER {val}')

    def _get_aperture_time(self):
        if self.Mode == 'SrcV_MeasI':
            return self.ask(':SENS:CURR:APER?')
        else:
            return self.ask(':SENS:VOLT:APER?')
 
    def _estimate_sweep_time(self):
        sweep_points = int(self.SweepSamplePoints)
        if self.SweepRepeat == 'DOUB':
            points = 2*sweep_points
        else:
            points = sweep_points
        aperture_time = float(self.SweepSampleTime)
        trig_source_delay = float(self.TriggerSourceDelay)
        trig_acq_delay = float(self.TriggerAcquisitionDelay)
        sweep_total_time = points * (aperture_time + trig_source_delay + trig_acq_delay)
        return sweep_total_time
    
    def _start_dwell(self):
        '''Function let the system dwell at the beginning of the measurement
        currently not used'''
        first_val = self.SweepStartValue
        self.write(':OUTP:PROT ON')
        self.write(':SOUR:WAIT ON')
        self.write(':SOUR:WAIT:AUTO OFF')
        self.write(f':SOUR:WAIT:OFFS {self._dwell_time}')
        # print(f"DEBUG: Starting dwell with first value {first_val} for dwell time {self._dwell_time} seconds")
        if self.Mode == 'SrcV_MeasI':
            self.write(':SOUR:VOLT:MODE FIX')
            self.volt_force(first_val)
        else:
            self.write(':SOUR:CURR:MODE FIX')
            self.current_force(first_val)

    def get_data(self):
            '''
            Function to handle Sweep and List Measurement
            '''
            assert self.SweepStartValue != self.SweepEndValue, "Must supply different values for the starting and ending values for the sweep..."
            assert self.SweepSamplePoints > 1, "Must have more than 1 sweeping point..."

            if self.SweepMode == 'SWE':
                if self.SweepRepeat == 'DOUB':
                    trig_points = int(self.SweepSamplePoints) * 2
                else:
                    trig_points = int(self.SweepSamplePoints)
            else:
                trig_points = int(self.SweepSamplePoints)
            # print(f"DEBUG: Trigger points set to {trig_points} based on sweep sample points {self.SweepSamplePoints}")

            sweep_total_time = self._estimate_sweep_time()

            # Generate trigger points by automatic internal algorithm
            self.write(':TRIG:SOUR AINT')
            self.write(f':TRIG:COUN {trig_points}')

            self.Output = True

            self.write(':INIT')
            # print("DEBUG: Initialized sweep, estimated sweep time (s): ", sweep_total_time)
            time.sleep(sweep_total_time) #wait for sweep to complete;
            # print("DEBUG: Sweep wait complete, fetching data...")

            currents_raw = self.ask(':FETC:ARR:CURR?').split(',')
            voltages_raw = self.ask(':FETC:ARR:VOLT?').split(',')

            currents = np.array([float(x) for x in currents_raw])
            voltages = np.array([float(x) for x in voltages_raw])

            self.Output = False

            data_pkt = {
                        'parameters' : ['Points'],
                        'data' : { 'Current' : currents, 'Voltage' : voltages }
                    }

            return {'data': data_pkt}