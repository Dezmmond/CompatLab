class CommandExit(Exception):
    def __init__(self, code: int = 0) -> None:
        self.code = code
        super().__init__(code)
