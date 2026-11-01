import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api.v1.endpoints import health, patients

app = FastAPI(
    title="MediTriage API",
    version="0.1.0",
    description="Backend base para MediTriage"
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")

_PROBLEM_BASE = "https://api.meditriage.com/problems"


def _campo(loc) -> str:
    # loc = ("body", "rut") -> "rut"
    return ".".join(str(x) for x in loc if x not in ("body", "query", "path"))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """422 con el formato de api/examples/validation-error-422.json."""
    errores = [
        {
            "field": _campo(e["loc"]),
            # Pydantic antepone "Value error, " a los mensajes de nuestros validadores.
            "message": e["msg"].removeprefix("Value error, "),
        }
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "type": f"{_PROBLEM_BASE}/validation-error",
            "title": "Error de validación",
            "status": 422,
            "detail": "; ".join(f"{e['field']}: {e['message']}" for e in errores),
            "instance": request.url.path,
            "errors": errores,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    titulos = {409: "Conflicto", 404: "No encontrado", 403: "Prohibido", 401: "No autorizado"}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": f"{_PROBLEM_BASE}/{exc.status_code}",
            "title": titulos.get(exc.status_code, "Error"),
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": request.url.path,
        },
        headers=exc.headers,
    )

@app.get("/")
def root():
    return {"message": "Servidor MediTriage activo", "docs": "/docs"}

if __name__ == "__main__":
    # Lee el puerto de la variable de entorno $PORT, si no existe usa 8000
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=puerto, reload=True)