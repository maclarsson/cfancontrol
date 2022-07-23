
class Sensor(object):

    def __init__(self):
        self.sensor_name = None

    def get_name(self) -> str:
        return self.sensor_name

    def get_temperature(self) -> float:
        raise NotImplementedError()

    def get_signature(self) -> list:
        raise NotImplementedError()


class DummySensor(Sensor):

    def __init__(self) -> None:
        super().__init__()
        self.sensor_name = "<none>"
        self.current_temp = 0.0

    def get_temperature(self) -> float:
        return self.current_temp

    def get_signature(self) -> list:
        return [__class__.__name__, "dummy", "", self.sensor_name, 0]