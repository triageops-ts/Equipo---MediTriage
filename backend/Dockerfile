# ==========================================
# ETAPA 1: Builder (Compilación y dependencias)
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Dependencias del sistema para compilar librerías C/PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar en carpeta aislada (/install)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ==========================================
# ETAPA 2: Runtime (python:3.11-slim, Debian 13, con parches de seguridad al día)
# ==========================================
# Antes era distroless/python3-debian12. Se cambió porque esa imagen base no recibe
# a tiempo los parches de Debian y container-scan (Trivy) bloqueaba por 45 CVE
# HIGH/CRITICAL con parche disponible (libssl3, python3.11-minimal, etc.).
FROM python:3.11-slim

# Aplicar los parches de seguridad publicados por Debian y crear el usuario sin privilegios
# (mismo uid 65532 que usaba distroless "nonroot").
# setuptools y wheel solo sirven para instalar paquetes, no para ejecutar la app.
# Se quitan porque traen copias vendorizadas con CVE HIGH (jaraco.context, wheel).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && pip uninstall -y setuptools wheel \
    && useradd --uid 65532 --no-create-home --shell /usr/sbin/nologin nonroot

WORKDIR /app

# Copiar librerías desde el builder
COPY --from=builder /install/lib/python3.11/site-packages /site-packages

# Copiar el código fuente asegurando permisos para el usuario nonroot
COPY --chown=nonroot:nonroot app ./app

# Alembic (migraciones de base de datos)
COPY --chown=nonroot:nonroot alembic.ini ./alembic.ini
COPY --chown=nonroot:nonroot migrations ./migrations

# Factor 07: Puerto por defecto 8000 y rutas de importación de Python
ENV PORT=8000
ENV PYTHONPATH="/site-packages:/app"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

USER nonroot

# Reutiliza el arranque de main.py (lee $PORT con fallback a 8000)
CMD ["python", "app/main.py"]