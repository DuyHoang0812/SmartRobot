class AppError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = 401,
        *,
        clear_cookies: bool = False,
        headers: dict[str, str] | None = None,
    ):
        self.detail = detail
        self.status_code = status_code
        self.clear_cookies = clear_cookies
        self.headers = headers or ({"WWW-Authenticate": "Bearer"} if status_code == 401 else {})


class AuthError(AppError):
    pass
