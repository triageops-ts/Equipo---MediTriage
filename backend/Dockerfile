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
# ETAPA 2: Runtime Distroless (Debian 12 / Python 3.11)
# ==========================================
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

# Copiar librerías desde el builder
COPY --from=builder /install/lib/python3.11/site-packages /site-packages

# Copiar el código fuente asegurando permisos para el usuario nonroot
COPY --chown=nonroot:nonroot app ./app

# Factor 07: Puerto por defecto 8000 y rutas de importación de Python
ENV PORT=8000
ENV PYTHONPATH="/site-packages:/app"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Reutiliza el arranque de main.py (lee $PORT con fallback a 8000)
CMD ["app/main.py"]