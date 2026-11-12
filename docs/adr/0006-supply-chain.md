# ADR 0006: Política de Firma de Imágenes, Trazabilidad SLSA y Control de Admisión

## Estado
Aceptado

## Contexto
El proyecto MediTriage requiere asegurar la cadena de suministro de software en la infraestructura de contenedores, garantizando que el clúster de Kubernetes solo despliegue imágenes de backend cuya integridad, autoría y origen estén verificados criptográficamente.

## Decisión
Se implementa una estrategia integral de seguridad en el pipeline de CI/CD (GitHub Actions) y en el clúster:
1. **Firma digital Keyless:** Se utiliza **Cosign** integrado con OIDC (OpenID Connect) para firmar las imágenes del backend de manera nativa sin gestión manual de llaves privadas.
2. **Nivel de seguridad SLSA:** Se adopta el nivel **SLSA Nivel 2**, generando un `provenance.json` mediante `cosign attest --type slsaprovenance` que certifica que la imagen fue construida en un entorno hospedado automatizado (GitHub Actions).
3. **Control de admisión en el clúster:** Se implementa una política de **Kyverno** (`require-image-signature`) en el namespace del equipo para que el clúster rechace de forma automática cualquier imagen que carezca de una firma digital válida generada por el proceso oficial.

## Consecuencias
* **Positivas:** Trazabilidad completa desde el código fuente hasta el clúster, rechazo automático de contenedores no autorizados o alterados, y automatización estricta sin secretos de firma estáticos.
* **Negativas:** Estricta dependencia de la disponibilidad del emisor OIDC de Sigstore y del correcto funcionamiento del runner durante la atestación.
