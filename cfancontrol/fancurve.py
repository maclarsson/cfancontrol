from typing import List, Optional
from enum import Enum

MINTEMP = 0
MAXTEMP = 100
MINPWM = 0
MAXPWM = 255
MAXPERCENTAGE = 100


class FanMode(Enum):
    Off = 0
    Fixed = 1
    Curve = 2


class TempRange:

    def __init__(self, low=0.0, high=0.0, start=0, end=MAXPERCENTAGE, hyst=0.0) -> None:
        self.low_temp: float = low
        self.high_temp: float = high
        self.pwm_start: int = int((float(start) / 100) * MAXPWM)
        self.pwm_end: int = int((float(end) / 100) * MAXPWM)
        self.hysteresis: float = hyst


class FanCurve:

    @classmethod
    def pwm_to_percentage(cls, pwm: int) -> int:
        percent = int(round(float((pwm / MAXPWM) * MAXPERCENTAGE), 0))
        return percent
    
    @classmethod
    def percentage_to_pwm(cls, percent: int) -> int:
        pwm = int(round(float((percent / MAXPERCENTAGE) * MAXPWM), 0))
        return pwm

    @staticmethod
    def zero_rpm_curve() -> 'FanCurve':
        zero_curve = FanCurve([TempRange(MINTEMP, MAXTEMP, MINPWM, MINPWM, 0.0)])
        return zero_curve

    @staticmethod
    def fixed_speed_curve(speed: int) -> 'FanCurve':
        fixed_curve = FanCurve([TempRange(MINTEMP, MAXTEMP, speed, speed, 0.0)])
        return fixed_curve
    
    @staticmethod
    def full_speed_curve() -> 'FanCurve':
        full_speed_curve = FanCurve([TempRange(MINTEMP, MAXTEMP, MAXPWM, MAXPWM, 0.0)])
        return full_speed_curve

    @staticmethod
    def linear_curve() -> 'FanCurve':
        linear_curve = FanCurve([TempRange(0, 20, 0, 20, 0.0),
                                 TempRange(20, 40, 20, 40, 0.0),
                                 TempRange(40, 60, 40, 60, 0.0),
                                 TempRange(60, 80, 60, 80, 0.0),
                                 TempRange(80, 100, 80, 100, 0.0)])
        return linear_curve

    @staticmethod
    def exponential_curve() -> 'FanCurve':
        exponential_curve = FanCurve([TempRange(0, 20, 0, 0, 0.0),
                                      TempRange(20, 40, 0, 10, 0.0),
                                      TempRange(40, 60, 10, 30, 0.0),
                                      TempRange(60, 80, 30, 60, 0.0),
                                      TempRange(80, 100, 60, 100, 0.0)])
        return exponential_curve

    @staticmethod
    def semi_exponential_curve() -> 'FanCurve':
        semi_exponential_curve = FanCurve([TempRange(0, 0, 0, 20, 0.0),
                                           TempRange(0, 20, 20, 20, 0.0),
                                           TempRange(20, 50, 20, 30, 0.0),
                                           TempRange(50, 80, 30, 60, 0.0),
                                           TempRange(80, 100, 60, 100, 0.0)])
        return semi_exponential_curve

    @staticmethod
    def logistic_curve() -> 'FanCurve':
        logistic_curve = FanCurve([TempRange(0, 20, 0, 10, 0.0),
                                   TempRange(20, 40, 10, 35, 0.0),
                                   TempRange(40, 60, 35, 70, 0.0),
                                   TempRange(60, 80, 70, 90, 0.0),
                                   TempRange(80, 100, 90, 100, 0.0)])
        return logistic_curve

    @staticmethod
    def semi_logistic_curve() -> 'FanCurve':
        semi_logistic_curve = FanCurve([TempRange(0, 40, 0, 0, 0.0),
                                        TempRange(40, 40, 40, 40, 0.0),
                                        TempRange(40, 60, 40, 70, 0.0),
                                        TempRange(60, 80, 70, 90, 0.0),
                                        TempRange(80, 100, 90, 100, 0.0)])
        return semi_logistic_curve

    def __init__(self, ranges: List[TempRange] = None):
        if ranges is None:
            self._temp_ranges = list()
        else:
            self._temp_ranges = ranges
        self._set_fan_mode()
        self._active_range: Optional[TempRange] = None

    def _set_fan_mode(self):
        if len(self._temp_ranges) == 0:
            self._fan_mode = FanMode.Off
        elif len(self._temp_ranges) > 1:
            self._fan_mode = FanMode.Curve
        else:
            if self._temp_ranges[0].pwm_end > 0:
                self._fan_mode = FanMode.Fixed
            else:
                self._fan_mode = FanMode.Off

    def get_fan_mode(self) -> FanMode:
        return self._fan_mode

    def add_range(self, temp_range: TempRange) -> None:
        self._temp_ranges.append(temp_range)
        self._set_fan_mode()

    def get_first_range(self) -> TempRange:
        return self._temp_ranges[0]

    def get_last_range(self) -> TempRange:
        return self._temp_ranges[-1]

    def get_ranges(self) -> list:
        return self._temp_ranges

    def get_curve_fixed_speed(self) -> int:
        if self._fan_mode == FanMode.Fixed:
            if len(self._temp_ranges) == 1:
                return FanCurve.pwm_to_percentage(self.get_last_range().pwm_end)
            else:
                return 0
        else:
            return 0
    
    def get_range_from_temp(self, temp: float) -> TempRange:
        if self._active_range is not None:
            if self._active_range.hysteresis > 0.0:
                temp = temp + self._active_range.hysteresis

        self._active_range = None
        for temp_range in self._temp_ranges:
            if temp < temp_range.high_temp:
                self._active_range = temp_range
                break
        return self._active_range

    def get_graph_points_from_curve(self) -> list:
        points = [[int(self.get_first_range().low_temp), self.pwm_to_percentage(self.get_first_range().pwm_start)]]
        for temp_range in self.get_ranges():
            points.append([int(temp_range.high_temp), self.pwm_to_percentage(temp_range.pwm_end)])
        return points

    def set_curve_from_graph_points(self, points: list):
        self._temp_ranges.clear()
        if points is not None:
            if len(points) > 1:
                for i in range(0, len(points) - 1):
                    self.add_range(TempRange(points[i][0], points[i + 1][0], points[i][1], points[i + 1][1], 0.0))
            else:
                self.add_range(TempRange(MINTEMP, MAXTEMP, MINPWM, MINPWM, 0.0))
        else:
            self.add_range(TempRange(MINTEMP, MAXTEMP, MINPWM, MINPWM, 0.0))





