class AppError(Exception):
    """Erro de dominio convertido para resposta HTTP pelo handler global."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class BadRequestError(AppError):
    def __init__(self, detail: str):
        super().__init__(400, detail)


class UnauthorizedError(AppError):
    def __init__(self, detail: str):
        super().__init__(401, detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str):
        super().__init__(403, detail)


class NotFoundError(AppError):
    def __init__(self, detail: str):
        super().__init__(404, detail)


class ServiceUnavailableError(AppError):
    def __init__(self, detail: str):
        super().__init__(503, detail)
