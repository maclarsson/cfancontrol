
from .sensor import Sensor
from .fancurve import FanCurve, FanMode, TempRange
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

    def update_pwm(self) -> (bool, int, int, float):
        new_pwm: int
        pwm_percent: float
        temp: float
        temp_range: TempRange

        if self.fan_curve.get_fan_mode() == FanMode.Off:
            new_pwm = 0
            pwm_percent = 0.0
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
                LogManager.logger.warning(f"'{self.fan_name}': no suitable range for temp [" + str(temp) + "] found")
                return False, 0, 0

            LogManager.logger.debug(f"{self.fan_name}': current temp " + str(temp) + "°C (+" + str(temp_range.hysteresis) + "°C hysteresis) in range [" + str(temp_range.low_temp) + "°C] to [" + str(temp_range.high_temp) + "°C]")
            if temp < temp_range.low_temp:
                temp = temp_range.low_temp
            if temp_range.hysteresis > 0.0:
                temp = temp + temp_range.hysteresis

            percentile = (temp - temp_range.low_temp) / (temp_range.high_temp - temp_range.low_temp)
            pwm_float = temp_range.pwm_start + (percentile * (temp_range.pwm_end - temp_range.pwm_start))
            new_pwm = int(pwm_float)
            pwm_percent = self.fan_curve.pwm_to_percentage(new_pwm)

        if new_pwm != self.pwm:
            LogManager.logger.debug(f"'{self.fan_name}': new target PWM {new_pwm} in range [{str(temp_range.pwm_start)}] to [{str(temp_range.pwm_end)}]")
        else:
            LogManager.logger.debug(f"'{self.fan_name}': new target PWM same as current PWM")

        return (new_pwm != self.pwm), new_pwm, pwm_percent, temp

