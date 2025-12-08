class HttpException(Exception):
    """
    Custom HTTP exception that can be used to report user-facing errors that will be rendered
    in a custom error page.
    """

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

    def __str__(self):
        return self.message


class HttpException400(HttpException):
    def __init__(self, message="The client request was invalid."):
        super().__init__(400, message)


class HttpException404(HttpException):
    def __init__(self, message="The page you requested does not exist."):
        super().__init__(404, message)


class HttpException403(HttpException):
    def __init__(self, message="You are not permitted to view this page."):
        super().__init__(403, message)


class HttpException409(HttpException):
    def __init__(
        self,
        message="Request could not be processed because of conflict in the current state of the resource.",
    ):
        super().__init__(409, message)


class HttpException429(HttpException):
    def __init__(
        self,
        message="You sent too many requests in a given amount of time.",
    ):
        super().__init__(429, message)
