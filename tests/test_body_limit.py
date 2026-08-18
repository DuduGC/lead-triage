import asyncio

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.middleware import BodySizeLimitMiddleware


def test_body_size_limit_rejects_payload_before_route():
    application = FastAPI()
    application.add_middleware(BodySizeLimitMiddleware, max_body_bytes=32)

    @application.post("/echo")
    async def echo(request: Request):
        return JSONResponse({"size": len(await request.body())})

    async def send_request():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/echo", json={"message": "x" * 100})

    response = asyncio.run(send_request())

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "PAYLOAD_TOO_LARGE",
            "message": "Request body is too large",
        }
    }


def test_body_size_limit_preserves_valid_body_for_route():
    application = FastAPI()
    application.add_middleware(BodySizeLimitMiddleware, max_body_bytes=32)

    @application.post("/echo")
    async def echo(request: Request):
        return JSONResponse({"size": len(await request.body())})

    async def send_request():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/echo", content=b"small")

    response = asyncio.run(send_request())

    assert response.status_code == 200
    assert response.json() == {"size": 5}
