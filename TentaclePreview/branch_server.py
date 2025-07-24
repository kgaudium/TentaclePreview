
class BranchServer:
    def __init__(self, name: str):
        self.name: str = name
        self._port: int | None = None
        self.hasUpdate: bool = True
        self.isBuildSuccess: bool | None = None
        self.isStartSuccess: bool | None = None
        self.buildError: str | None = None
        self.startError: str | None = None

    def start(self):
        pass

    def stop(self):
        pass

    def build(self):
        pass

    @property
    def port(self) -> int | None:
        return self._port

    @port.setter
    def port(self, value) -> None:
        pass