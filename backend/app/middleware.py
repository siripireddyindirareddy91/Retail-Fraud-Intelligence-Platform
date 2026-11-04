import json
import logging
import time
from uuid import uuid4

from starlette.responses import JSONResponse


class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        for key in ("request_id", "method", "path", "status", "duration_ms", "job_id"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exception_type"] = record.exc_info[0].__name__
        return json.dumps(data)


def configure_logging(level):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("retail")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


class RequestMiddleware:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        status = 500

        async def logged_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.extend([(b"x-request-id", request_id.encode()), (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"same-origin"), (b"cache-control", b"no-store")])
                message = {**message, "headers": headers}
            await send(message)

        try:
            if scope["method"] in {"POST", "PUT", "PATCH"}:
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > self.max_bytes:
                        response = JSONResponse({"error": {"code": "body_too_large", "message": "Request body exceeds the configured limit.", "details": None, "request_id": request_id}}, status_code=413)
                        return await response(scope, receive, logged_send)
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
                original_receive, consumed = receive, False
                async def replay():
                    nonlocal consumed
                    if not consumed:
                        consumed = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await original_receive()
                receive = replay
            await self.app(scope, receive, logged_send)
        finally:
            logging.getLogger("retail.http").info("request_completed", extra={"request_id": request_id, "method": scope["method"], "path": scope["path"], "status": status, "duration_ms": round((time.monotonic() - started) * 1000)})
