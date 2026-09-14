import time
import logging
from uuid import uuid4
from fastapi import Request

logger = logging.getLogger("api.requests")


async def request_logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or f"req-{uuid4().hex[:16]}"
    request.state.trace_id = trace_id
    inicio = time.perf_counter()
    response = await call_next(request)
    duracao = (time.perf_counter() - inicio) * 1000

    logger.info(
        "request_completed method=%s path=%s status=%d duration_ms=%.0f trace_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duracao,
        trace_id,
    )
    response.headers["X-Trace-Id"] = trace_id
    return response
