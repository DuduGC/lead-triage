from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before route validation runs."""

    def __init__(self, app, max_body_bytes: int):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                return self._too_large_response()
            if declared_length > self.max_body_bytes:
                return self._too_large_response()

        body = await request.body()
        if len(body) > self.max_body_bytes:
            return self._too_large_response()

        return await call_next(request)

    @staticmethod
    def _too_large_response() -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": "Request body is too large",
                }
            },
        )
