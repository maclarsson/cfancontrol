
from .sensor import Sensor
from .fancurve import FanCurve, FanMode, TempRange, MAXPWM
from .log import LogManager


class PWMFan:

    def __init__(self, name: str, curve: FanCurve, sensor: Sensor) -> None:
        self.fan_name = name
        self.fan_curve: FanCurve = curve
        self.temp_sensor: Sensor = sensor
        self.pwm = 0
        self.temperature = 0.0

    def get_current_pwm(self) -> int:
        return self.pwm

    def set_current_pwm(self, pwm: int) -> None:
        self.pwm = pwm
        return

    def get_current_pwm_as_percentage(self) -> int:
        return FanCurve.pwm_to_percentage(self.pwm)

    def get_current_temp(self) -> float:
        self.temperature = self.temp_sensor.get_temperature()
        return self.temperature

    def get_fan_status(self) -> (FanMode, int, int, float):
        return self.fan_curve.get_fan_mode(), self.get_current_pwm(), self.get_current_pwm_as_percentage(), self.get_current_temp()

    def update_pwm(self, current_pwm: int) -> (bool, int, int, float):
        new_pwm: int
        pwm_percent: int
        temp: float
        temp_range: TempRange

        if self.pwm != current_pwm:
            if 0 < current_pwm <= MAXPWM:
                LogManager.logger.warning(f"Fan speed changed unexpectedly {repr({'fan': self.fan_name, 'expected pwm': self.pwm, 'reported pwm': current_pwm})}")
                self.pwm = current_pwm

        if self.fan_curve.get_fan_mode() == FanMode.Off:
            new_pwm = 0
            pwm_percent = 0
            temp = 0.0
            return (new_pwm != self.pwm), new_pwm, pwm_percent, temp

        if self.fan_curve.get_fan_mode() == FanMode.Fixed:
            temp = 0.0
            temp_range = self.fan_curve.get_range_from_temp(temp)
            percentile = (temp - temp_range.low_temp) / (temp_range.high_temp - temp_range.low_temp)
            pwm_float = temp_range.pwm_start + (percentile * (temp_range.pwm_end - temp_range.pwm_start))
            new_pwm = int(pwm_float)
            pwm_percent = self.fan_curve.pwm_to_percentage(new_pwm)
        else:
            temp = self.get_current_temp()
            temp_range = self.fan_curve.get_range_from_temp(temp)

            if temp_range is None:
                LogManager.logger.warning(f"No suitable temperature range found {repr({'fan': self.fan_name, 'temperature': str(temp)})}")
                return False, 0, 0

            if temp < temp_range.low_temp:
                temp = temp_range.low_temp
            if temp_range.hysteresis > 0.0:
                temp = temp + temp_range.hysteresis

            percentile = (temp - temp_range.low_temp) / (temp_range.high_temp - temp_range.low_temp)
            pwm_float = temp_range.pwm_start + (percentile * (temp_range.pwm_end - temp_range.pwm_start))
            new_pwm = int(pwm_float)
            pwm_percent = self.fan_curve.pwm_to_percentage(new_pwm)

        if new_pwm != self.pwm:
            LogManager.logger.debug(f"Changing PWM {repr({'fan': self.fan_name, 'current pwm': self.pwm, 'target pwm': new_pwm, 'target range': f'[{temp_range.pwm_start}-{temp_range.pwm_end}]', 'temperature range': f'[{temp_range.low_temp}-{temp_range.high_temp}]°C'})}")

        return (new_pwm != self.pwm), new_pwm, pwm_percent, temp

