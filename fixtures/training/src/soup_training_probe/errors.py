class ContractError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
