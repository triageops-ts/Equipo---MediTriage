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

## Alternativas descartadas
* **Firma con par de llaves gestionado por el equipo (Cosign con llave privada):** se descartó porque obliga a guardar y rotar una llave privada como secreto del pipeline, lo que es justo lo que la firma keyless con OIDC evita.
* **No firmar y confiar solo en el tag con el SHA del commit:** se descartó porque el tag identifica una versión, pero no prueba quién construyó la imagen ni dónde. Cualquiera con acceso al registro podría publicar una imagen con ese tag.
* **SLSA Nivel 3 (builder aislado y verificado):** se descartó porque exige más infraestructura y configuración de la que el alcance del MVP justifica. El Nivel 2 ya certifica que la imagen salió de un entorno automatizado (GitHub Actions).
* **Sin control de admisión (verificar la firma solo en el pipeline):** se descartó porque el clúster aceptaría igual una imagen sin firma subida por otra vía. Kyverno rechaza esas imágenes en el momento del despliegue.

## Consecuencias
* **Positivas:** Trazabilidad completa desde el código fuente hasta el clúster, rechazo automático de contenedores no autorizados o alterados, y automatización estricta sin secretos de firma estáticos.
* **Negativas:** Estricta dependencia de la disponibilidad del emisor OIDC de Sigstore y del correcto funcionamiento del runner durante la atestación.
