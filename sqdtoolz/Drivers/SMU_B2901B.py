import sys

from qcodes import VisaInstrument, validators as vals
import numpy as np

class SMU_B2901B(VisaInstrument):
    """This class represents and controls a Keysight B2901B SMU. For operating
    details of this instrument, refer to Keysight document B2910-90030, titled
    "Keysight B2900 SCPI Command Reference". Expanded with fast sweep/list mode."""

    MAX_LIST_POINTS = 100000
    LIST_UPLOAD_CHUNK_SIZE = 1000

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, **kwargs)

        self.description = "Keysight B2901 SMU"
        self.expectedMfr = "Keysight Technologies"
        self.expectedModel = "B2901B"
        self.VID = 0x0957
        self.PID = 0x8b18
        # A reconnect must never inherit an active or unprotected output.
        # Configure protection before any source or range setting is changed.
        self._write_checked(':OUTP OFF')
        self._write_checked(':OUTP:PROT ON')

        # Source and measurement range are independent on the B2900B.
        for command in (
            ':SOUR:VOLT:RANG:AUTO ON',
            ':SOUR:CURR:RANG:AUTO ON',
            ':SENS:VOLT:RANG:AUTO ON',
            ':SENS:CURR:RANG:AUTO ON',
        ):
            self._write_checked(command)

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
        

        self._sweep_list = None
        self._sweep_list_mode = None

    @property
    def Mode(self):
        return self.mode()
    @Mode.setter
    def Mode(self, mode):
        if mode not in ('SrcV_MeasI', 'SrcI_MeasV'):
            raise ValueError('Mode must be SrcV_MeasI or SrcI_MeasV')
        self._ensure_output_off('changing source mode')
        self.mode(mode)
        self._raise_if_instrument_error('setting source mode')
        self._write_checked(':OUTP:PROT ON')
        if mode == 'SrcV_MeasI':
            self._write_checked(':SENS:FUNC "CURR"')
        else:
            self._write_checked(':SENS:FUNC "VOLT"')

    @property
    def Output(self):
        return self.output()
    @Output.setter
    def Output(self, val):
        if val:
            self._write_checked(':OUTP:PROT ON')
            self.output(True)
            self._raise_if_instrument_error('enabling output')
        else:
            self._abort_and_disable_output()
            self._wait_for_operation_complete(5.0)
        self._last_user_output_state = bool(val)

    @property
    def Voltage(self):
        return self.volt_force()
    @Voltage.setter
    def Voltage(self, val):
        self.volt_force(val)

    @property
    def Current(self):
        return self.current_force()
    @Current.setter
    def Current(self, val):
        self.current_force(val)

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
        if self.SweepMode == 'LIST':
            return self._get_active_sweep_list().size
        if self.mode() == 'SrcV_MeasI':
            return self.sweep_v_points()
        else:
            return self.sweep_i_points()

    @SweepSamplePoints.setter
    def SweepSamplePoints(self, val):
        if self.SweepMode == 'LIST':
            raise ValueError('LIST sweep point count is defined by SweepList')
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
        return self._get_sweep_mode()
    @SweepMode.setter
    def SweepMode(self, val):
        if val not in ('SWE', 'LIST'):
            raise ValueError('Sweep mode must be SWE or LIST')
        self._ensure_output_off('changing sweep mode')
        self._set_sweep_mode(val)
        self._raise_if_instrument_error('setting sweep mode')
        if self.SweepMode != val:
            raise RuntimeError(f'B2901B did not enter {val} sweep mode')
    
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
        self._set_sweep_list(val)

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
        if self.SweepMode == 'SWE':
            self.write(f':SOUR:SWE:STA {val.upper()}')

    def _get_sweep_dir_mode(self):
        if self.SweepMode == 'LIST':
            return 'SING'
        if self.SweepMode == 'SWE':
            return self.ask(':SOUR:SWE:STA?').strip()

    def _set_sweep_list(self, val):
        self._ensure_output_off('programming SweepList')
        if self.SweepMode != 'LIST':
            raise RuntimeError('Set SweepMode to LIST before programming SweepList')

        source_function, source_limit = self._active_list_source()
        values = self._validate_sweep_list(val, source_limit)
        formatted_values = [format(value, '.17g') for value in values]
        for start_index in range(0, values.size, self.LIST_UPLOAD_CHUNK_SIZE):
            command_suffix = '' if start_index == 0 else ':APP'
            value_chunk = formatted_values[
                start_index:start_index + self.LIST_UPLOAD_CHUNK_SIZE
            ]
            self._write_checked(
                f':SOUR:LIST:{source_function}{command_suffix} {",".join(value_chunk)}'
            )

        programmed_points = self._get_programmed_list_points(source_function)
        if programmed_points != values.size:
            raise RuntimeError(
                'B2901B did not accept the complete list: '
                f'uploaded {values.size} points, instrument reports {programmed_points}'
            )

        self._sweep_list = values
        self._sweep_list_mode = self.Mode
        
    def _get_sweep_list(self):
        return self._get_active_sweep_list().copy()

    def _active_list_source(self):
        if self.Mode == 'SrcV_MeasI':
            return 'VOLT', 210.0
        if self.Mode == 'SrcI_MeasV':
            return 'CURR', 3.0
        raise ValueError('Invalid source mode for SweepList')

    def _validate_sweep_list(self, values, source_limit):
        if not isinstance(values, (list, tuple, np.ndarray)):
            raise TypeError('SweepList must be a one-dimensional list, tuple, or numpy array')

        raw_values = np.asarray(values, dtype=object)
        if raw_values.ndim != 1:
            raise ValueError('SweepList must be one-dimensional')
        if raw_values.size < 2:
            raise ValueError('SweepList must contain at least two points')
        if raw_values.size > self.MAX_LIST_POINTS:
            raise ValueError(
                f'SweepList exceeds the {self.MAX_LIST_POINTS}-point instrument limit'
            )
        if any(
            isinstance(value, (bool, np.bool_, str, bytes, complex, np.complexfloating))
            for value in raw_values
        ):
            raise ValueError('SweepList values must be real numbers')

        try:
            numeric_values = np.asarray(values, dtype=float)
        except (TypeError, ValueError) as error:
            raise ValueError('SweepList values must be real numbers') from error

        if not np.isfinite(numeric_values).all():
            raise ValueError('SweepList values must be finite')
        if np.any(np.abs(numeric_values) > source_limit):
            raise ValueError(
                f'SweepList values must be within +/-{source_limit:g} of the active source'
            )
        return numeric_values.copy()

    def _get_programmed_list_points(self, source_function):
        response = self.ask(f':SOUR:LIST:{source_function}:POIN?').strip()
        self._raise_if_instrument_error('verifying SweepList')
        try:
            return int(response)
        except ValueError as error:
            raise RuntimeError(
                f'Unexpected B2901B list-point response: {response!r}'
            ) from error

    def _get_active_sweep_list(self):
        if self._sweep_list is None:
            raise RuntimeError('No SweepList has been programmed')
        if self._sweep_list_mode != self.Mode:
            raise RuntimeError(
                'SweepList belongs to the previous source mode; program a new list'
            )
        return self._sweep_list

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

    def _raise_if_instrument_error(self, context):
        error = self.ask(':SYST:ERR?').strip()
        if error.startswith(('+0', '0')):
            return
        raise RuntimeError(f'B2901B error while {context}: {error}')

    def _write_checked(self, command):
        self.write(command)
        self._raise_if_instrument_error(f'executing {command!r}')

    def _abort_and_disable_output(self):
        """Best-effort abort followed by the command that stops output."""
        try:
            self.write(':ABOR')
        except Exception:
            # :OUTP OFF also stops a measurement, so it is still the essential
            # cleanup command if the abort itself fails.
            pass
        self.write(':OUTP OFF')
        if hasattr(self, '_last_user_output_state'):
            self._last_user_output_state = False

    def _ensure_output_off(self, operation):
        if self.Output:
            raise RuntimeError(f'Disable the output before {operation}')
        self._wait_for_operation_complete(5.0)
        if self.Output:
            raise RuntimeError(f'B2901B output remained enabled before {operation}')
        self._raise_if_instrument_error(f'before {operation}')

    def _wait_for_operation_complete(self, minimum_timeout):
        """Wait for the instrument rather than estimating sweep completion."""
        original_timeout = self.timeout()
        temporary_timeout = (
            None if original_timeout is None
            else max(float(original_timeout), float(minimum_timeout))
        )

        if temporary_timeout != original_timeout:
            self.timeout(temporary_timeout)
        try:
            if self.ask('*OPC?').strip() != '1':
                raise RuntimeError('B2901B did not report operation complete')
        finally:
            if temporary_timeout != original_timeout:
                self.timeout(original_timeout)
 
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
    
    def get_data(self):
        '''Function to handle sweep and list measurements.'''
        sweep_mode = self.SweepMode
        list_base_command = None
        if sweep_mode == 'LIST':
            list_values = self._get_active_sweep_list()
            source_function, _ = self._active_list_source()
            programmed_points = self._get_programmed_list_points(source_function)
            if programmed_points != list_values.size:
                raise RuntimeError(
                    'The programmed SweepList no longer matches the driver cache; '
                    'program the list again before starting a sweep'
                )
            trig_points = programmed_points
            list_base_command = (
                f':SOUR:{source_function} {format(list_values[0], ".17g")}'
            )
        elif sweep_mode == 'SWE':
            assert self.SweepStartValue != self.SweepEndValue, "Must supply different values for the starting and ending values for the sweep..."
            assert self.SweepSamplePoints > 1, "Must have more than 1 sweeping point..."
            if self.SweepRepeat == 'DOUB':
                trig_points = int(self.SweepSamplePoints) * 2
            else:
                trig_points = int(self.SweepSamplePoints)
        else:
            raise RuntimeError(f'Unsupported sweep mode: {sweep_mode!r}')

        # Completion is confirmed by *OPC?, which includes instrument settling and autoranging.
        sweep_timeout = self._estimate_sweep_time() + 5.0
        active_exception = None

        try:
            if list_base_command is not None:
                self._write_checked(list_base_command)
            # Generate trigger points by the automatic internal algorithm.
            self._write_checked(':TRIG:SOUR AINT')
            self._write_checked(f':TRIG:COUN {trig_points}')
            self.Output = True

            self.write(':INIT')
            self._wait_for_operation_complete(sweep_timeout)
            self._raise_if_instrument_error('running sweep')

            currents = np.array(
                [float(x) for x in self.ask(':FETC:ARR:CURR?').split(',')]
            )
            voltages = np.array(
                [float(x) for x in self.ask(':FETC:ARR:VOLT?').split(',')]
            )

            if currents.size != trig_points or voltages.size != trig_points:
                raise RuntimeError(
                    'B2901B returned an unexpected number of sweep points: '
                    f'expected {trig_points}, got {currents.size} current and '
                    f'{voltages.size} voltage values'
                )

            data_pkt = {
                'parameters': ['Points'],
                'data': {'Current': currents, 'Voltage': voltages},
            }
            return {'data': data_pkt}
        except BaseException:
            active_exception = sys.exc_info()
            raise
        finally:
            try:
                self._abort_and_disable_output()
            except Exception:
                if active_exception is None:
                    raise
                self.log.exception('Failed to safely disable the B2901B output')

    def close(self):
        try:
            self._abort_and_disable_output()
        except Exception:
            self.log.exception('Failed to safely disable the B2901B output during close')
        finally:
            super().close()
