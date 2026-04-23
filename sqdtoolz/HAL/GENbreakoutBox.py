from sqdtoolz.HAL.HALbase import HALbase
import numpy as np
import time

class GENbreakoutBox(HALbase):
    def __init__(self, hal_name, lab, instr_id):
        HALbase.__init__(self, hal_name)
        self._instr_id = instr_id
        self._instr_box = lab._get_instrument(instr_id)
        # Get all port names from the instrument's submodules
        self._ports = list(self._instr_box.submodules.keys())
        lab._register_HAL(self)

    @classmethod
    def fromConfigDict(cls, config_dict, lab):
        return cls(config_dict["Name"], lab, config_dict["instrument"])

    @property
    def Position(self):
        # Return a dict of all port positions
        return {port: getattr(self._instr_box, port).Position for port in self._ports}

    @Position.setter
    def Position(self, pos_input):
        """
        Set port positions. Accepts either:
        - dict: {'Port1': 'Pforce', 'Port2': 'Pground'}
        - array/list: [0, 1, 2] -> sets Port1 to state 0, Port2 to state 1, Port3 to state 2
        """
        if isinstance(pos_input, dict):
            # Existing dict behavior (backward compatible)
            for port, pos in pos_input.items():
                if port in self._ports:
                    getattr(self._instr_box, port).Position = pos
                else:
                    raise ValueError(f"Port {port} not found in breakout box.")
        else:
            pos_array = np.asarray(pos_input, dtype=int)
            
            if len(pos_array) > len(self._ports):
                raise ValueError(f"Array length {len(pos_array)} exceeds number of ports {len(self._ports)}")
            
            states = self.get_possible_contacts()
            for i, pos in enumerate(pos_array):
                if pos < 0 or pos >= len(states):
                    raise ValueError(f"Index {pos} out of range [0, {len(states)-1}] for states {states}")
                port = str(self._ports[i])
                print(f'Debug: port {port}')
                time.sleep(1.0)
                getattr(self._instr_box, port).Position = pos

    def get_possible_contacts(self):
        # Assume all ports have the same possible states (from the instrument)
        return self._instr_box.get_all_switch_contacts()

    def _get_current_config(self):
        ret_dict = {
            'Name': self.Name,
            'instrument': self._instr_id,
            'Type': self.__class__.__name__,
            'Position': self.Position  # Saves the full dict of positions
        }
        return ret_dict

    def _set_current_config(self, dict_config, lab):
        assert dict_config['Type'] == self.__class__.__name__, f'Cannot set configuration to a BreakoutBox with a config of type {dict_config["Type"]}'
        self.Position = dict_config['Position']  # Restores all positions