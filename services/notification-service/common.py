import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def create_app(service_name: str):
    app = FastAPI(title=service_name, version="1.0.0")
    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={
            "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred",
                      "request_id": getattr(request.state, "request_id", None)}
        })
    @app.get("/health")
    def health():
        return {"status": "ok", "service": service_name}
    return app
