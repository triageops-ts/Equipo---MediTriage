"""Headers de seguridad y CORS restringido (S11-1).

CORS: solo los orígenes de CORS_ORIGINS (separados por coma; por defecto el frontend local
http://localhost:3000). Nunca "*": la sesión viaja en una cookie y con credenciales el
navegador no admite "*". El frontend llama a la API a través del rewrite de Next (mismo
origen), así que CORS solo entra en juego si otro origen llama directo a la API.

Headers: se agregan a todas las respuestas HTTP (no a los WebSocket). El HSTS se omite con
ENVIRONMENT=development para que el navegador no fije https en localhost por un año.
"""
import os

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ORIGEN_POR_DEFECTO = "http://localhost:3000"

# La API solo devuelve JSON: no necesita cargar nada ni ser embebida en otra página.
CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# /docs (Swagger UI) y /redoc cargan scripts y estilos de un CDN y usan un script inline.
CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'"
)
RUTAS_DOCS = ("/docs", "/redoc")

HSTS = "max-age=31536000; includeSubDomains"

CABECERAS_FIJAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def es_desarrollo() -> bool:
    return os.environ.get("ENVIRONMENT", "").strip().lower() == "development"


def origenes_cors() -> list[str]:
    texto = os.environ.get("CORS_ORIGINS", ORIGEN_POR_DEFECTO)
    origenes = [o.strip().rstrip("/") for o in texto.split(",") if o.strip()]
    if "*" in origenes:
        raise RuntimeError("CORS_ORIGINS no puede incluir '*': la API usa cookies de sesión.")
    return origenes


def cabeceras_para(ruta: str) -> dict[str, str]:
    cabeceras = dict(CABECERAS_FIJAS)
    es_docs = any(ruta == r or ruta.startswith(r + "/") for r in RUTAS_DOCS)
    cabeceras["Content-Security-Policy"] = CSP_DOCS if es_docs else CSP_API
    if not es_desarrollo():
        cabeceras["Strict-Transport-Security"] = HSTS
    return cabeceras


class CabecerasSeguridadMiddleware:
    """Middleware ASGI puro: agrega los headers sin pisar los que ya puso el endpoint."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        cabeceras = cabeceras_para(scope.get("path", ""))

        async def enviar(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for nombre, valor in cabeceras.items():
                    headers.setdefault(nombre, valor)
            await send(message)

        await self.app(scope, receive, enviar)


def configurar_seguridad_http(app: FastAPI) -> None:
    # El último middleware agregado queda por fuera: los headers de seguridad también
    # salen en las respuestas que arma CORS (por ejemplo, el preflight OPTIONS).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes_cors(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["Retry-After"],
        max_age=600,
    )
    app.add_middleware(CabecerasSeguridadMiddleware)
