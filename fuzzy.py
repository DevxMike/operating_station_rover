import skfuzzy as fuzz
import numpy as np
from skfuzzy import control as ctrl

class navi:
    def __init__(self) -> None:
        Z = ctrl.Antecedent(np.arange(0, 100, 0.002), 'Z')
        THETA = ctrl.Antecedent(np.arange(-360, 360, 0.01), 'THETA')
        LEFT = ctrl.Consequent(np.arange(-100, 100, 1), "LEFT")
        RIGHT = ctrl.Consequent(np.arange(-100, 100, 1), "RIGHT")

        Z['ZERO'] = fuzz.trapmf(Z.universe, [0, 0, 0, 0])
        Z['S'] = fuzz.trimf(Z.universe, [0.001, 0.004, 0.004])
        Z['B'] = fuzz.trapmf(Z.universe, [0.002, 0.04, 100.5, 200])

        THETA['ZERO'] = fuzz.trimf(THETA.universe, [-5, 0, 5])
        THETA['M'] = fuzz.trimf(THETA.universe, [-648, -360, -6])
        THETA['P'] = fuzz.trimf(THETA.universe, [6, 360, 648])

        LEFT['MM'] = fuzz.gaussmf(LEFT.universe, -100, 30)
        RIGHT['MM'] = fuzz.gaussmf(RIGHT.universe, -100, 30)
        LEFT['SM'] = fuzz.gaussmf(LEFT.universe, -50, 8.918)
        RIGHT['SM'] = fuzz.gaussmf(RIGHT.universe, -50, 8.918)
        LEFT['MP'] = fuzz.gaussmf(LEFT.universe, 100, 30)
        RIGHT['MP'] = fuzz.gaussmf(RIGHT.universe, 100, 30)
        LEFT['SP'] = fuzz.gaussmf(LEFT.universe, -50, 8.918)
        RIGHT['SP'] = fuzz.gaussmf(RIGHT.universe, -50, 8.918)
        LEFT['ZERO'] = fuzz.trapmf(LEFT.universe, [0, 0, 0, 0])
        RIGHT['ZERO'] = fuzz.trapmf(RIGHT.universe, [0, 0, 0, 0])

        rule1 = ctrl.Rule(Z['ZERO'] & THETA['ZERO'], (LEFT['ZERO'], RIGHT['ZERO']))
        rule2 = ctrl.Rule(Z['ZERO'] & THETA['P'], (LEFT['ZERO'], RIGHT['ZERO']))
        rule3 = ctrl.Rule(Z['ZERO'] & THETA['M'], (LEFT['ZERO'], RIGHT['ZERO']))

        rule4 = ctrl.Rule(Z['S'] & THETA['ZERO'], (LEFT['SP'], RIGHT['SP']))
        rule5 = ctrl.Rule(Z['S'] & THETA['M'], (LEFT['SM'], RIGHT['SP']))
        rule6 = ctrl.Rule(Z['S'] & THETA['P'], (LEFT['SP'], RIGHT['SM']))

        rule7 = ctrl.Rule(Z['B'] & THETA['ZERO'], (LEFT['MP'], RIGHT['MP']))
        rule8 = ctrl.Rule(Z['B'] & THETA['M'], (LEFT['SM'], RIGHT['SP']))
        rule9 = ctrl.Rule(Z['B'] & THETA['P'], (LEFT['SP'], RIGHT['SM']))

        self.navi_ctrl = ctrl.ControlSystemSimulation(ctrl.ControlSystem([
            rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9
        ]))

    def get_output(self, Z, THETA):
        self.navi_ctrl.input['Z'] = Z
        self.navi_ctrl.input['THETA'] = THETA
        self.navi_ctrl.compute()
        return (self.navi_ctrl.output['LEFT'], self.navi_ctrl.output['RIGHT'])
        

    

    

