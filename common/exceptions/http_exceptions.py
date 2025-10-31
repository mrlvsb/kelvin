class HttpException(Exception):
    def __init__(self, code, message, title):
        self.code = code
        self.message = message
        self.title = title

    def __str__(self):
        return self.message


class HttpException400(HttpException):
    def __init__(self, message="Sorry, something was off in the request.", title="Bad Request"):
        super().__init__(400, message, title)


class HttpException404(HttpException):
    def __init__(self, message="The page you requested does not exist.", title="Page not found"):
        super().__init__(404, message, title)


class HttpException403(HttpException):
    def __init__(self, message="You are not permitted to view this page.", title="Forbidden"):
        super().__init__(403, message, title)


class HttpException409(HttpException):
    def __init__(
        self,
        message="Request could not be processed because of conflict in the current state of the resource.",
        title="Conflict",
    ):
        super().__init__(409, message, title)


class HttpException429(HttpException):
    def __init__(
        self,
        message="You sent too many requests in a given amount of time.",
        title="Too Many Requests",
    ):
        super().__init__(429, message, title)
