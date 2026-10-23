# ADR 0005: Estrategia de despliegue continuo con GitOps (Argo CD)

## Fecha
23/10/26

## Autores
Josefa Rodriguez, Lucas Benítez, Marcela Contreras, Isidora Ramos, Antonia Moya y Kimberlly Guillén

## Contexto
El ADR 0005 anterior definió el despliegue del servicio principal en Kubernetes local (Docker Desktop) y la creación de la infraestructura base (namespace y secrets) mediante Terraform. En esa entrega, los manifiestos de la aplicación se aplicaron de forma manual utilizando `kubectl apply -k`.

Para el Avance 8, se requiere automatizar el ciclo de entrega mediante un pipeline de Integración Continua (CI) en GitHub Actions y un flujo de Despliegue Continuo (CD) basado en GitOps, garantizando trazabilidad, seguridad y reconciliación automática entre los entornos de `dev` y `prod`.

La pauta establece las siguientes restricciones y requerimientos:
- Un pipeline de CI (`.github/workflows/ci.yml`) que ejecute gates de calidad (`ruff`, `pytest` con cobertura ≥ 80% y SAST con `Semgrep`) y publique la imagen en GitHub Container Registry (GHCR) tagueada con el Commit SHA (`${{ github.sha }}`).
- Un repositorio separado de GitOps (`triageops-gitops`) estructurado con Kustomize (`base/` y `overlays/{dev,prod}`).
- Instalación de Argo CD en el clúster para sincronizar automáticamente el estado deseado en Git.
- Un job de promoción (`promote`) que actualice el tag de la imagen en el repo GitOps tras compilar la aplicación.

## Decisión
Se adopta un modelo **GitOps basado en el enfoque Pull** mediante **Argo CD**, separando el código fuente de la aplicación de las declaraciones de infraestructura:

1. **Separación de Repositorios:**
   - **Repositorio de Aplicación (`Equipo---MediTriage`):** Aloja el código fuente, tests, configuración del CI (`ci.yml`) y la documentación técnica.
   - **Repositorio GitOps (`triageops-gitops`):** Aloja los manifiestos declarativos de Kubernetes organizados en `base/` y los entornos `overlays/dev` y `overlays/prod` mediante Kustomize.

2. **Infraestructura GitOps (Argo CD):**
   - Instalación de Argo CD en el namespace `argocd`.
   - Creación de la Application `meditriage-dev` apuntando a la ruta `overlays/dev` de la rama `main` en `triageops-gitops`, con destino al namespace `triageops` y sincronización automática (Auto-sync) activada.

3. **Estrategia de Promoción (Dev vs. Prod):**
   - **Promoción a Dev:** Automatizada a través del job `promote` en GitHub Actions, el cual actualiza el campo `newTag` en `overlays/dev/kustomization.yaml` con `${{ github.sha }}` mediante el token `GITOPS_TOKEN`. Argo CD detecta el cambio en Git y despliega la nueva versión.
   - **Promoción a Prod:** Controlada manualmente mediante Pull Request (PR) desde la carpeta de `dev` hacia `overlays/prod`.

## Razones de la decisión

### Enfoque Pull (Argo CD) vs. Push (GitHub Actions)
1. **Seguridad mejorada:** El clúster tira (pull) los cambios desde Git sin necesidad de almacenar credenciales administrativas del clúster de Kubernetes en GitHub Actions.
2. **Reconciliación y Autocuración:** Argo CD monitorea constantemente el clúster y corrige automáticamente cualquier desviación (*drift*) con respecto al estado deseado definido en Git.
3. **Única fuente de verdad (Single Source of Truth):** Toda modificación en el clúster queda registrada explícitamente en el historial de commits del repositorio `triageops-gitops`.

### Elección de Argo CD
1. **Observabilidad visual:** Proporciona una interfaz web (UI) intuitiva para auditar el estado de salud (*Healthy*) y sincronización (*Synced*) de los componentes.
2. **Soporte nativo para Kustomize:** Lee y renderiza directamente las estructuras de `base/` y `overlays/` sin necesidad de plugins externos.

### Separación en dos repositorios
Permite desvincular el ciclo de vida del desarrollo de software (código y pruebas) del ciclo de vida del despliegue (versiones e infraestructura), previniendo bucles infinitos en las ejecuciones del CI.

## Evidencia de verificación
- **Pipeline de CI:** Corridas verdes en GitHub Actions validando los gates de calidad (Linter, Tests y Semgrep) y la publicación de la imagen privada en GHCR.
- **Sincronización GitOps:** Application `meditriage-dev` en Argo CD en estado `Synced` y `Healthy`.
- **Flujo punta a punta:** Actualización automática del tag de la imagen en `overlays/dev/kustomization.yaml` y despliegue exitoso del nuevo pod en el namespace `triageops`.

Las capturas de evidencia se encuentran en el archivo `README.md` y en `docs/img/argocd-synced-healthy.png`.

## Alternativas descartadas

### Despliegue Push directo desde GitHub Actions
- **Razones de rechazo:** Exigía exponer credenciales del clúster al pipeline de CI y no ofrecía autocuración ante cambios manuales en el clúster.

### Flux CD
- **Razones de rechazo:** Aunque cumple la misma función GitOps, se prefirió Argo CD por su panel visual (UI), el cual simplifica la auditoría para todo el equipo.

## Consecuencias

### Positivas
- **Trazabilidad total:** Cada versión desplegada en el clúster corresponde exactamente al SHA de un commit del repositorio de código.
- **Automatización transparente:** Despliegues continuos en el ambiente de desarrollo tras pasar satisfactoriamente las pruebas de calidad y seguridad.
- **Seguridad en imágenes:** Uso del secreto `ghcr-secret` (`imagePullSecrets`) para autenticar el acceso a contenedores privados en GHCR.

### Negativas
- Necesidad de administrar y mantener dos repositorios distintos (`Equipo---MediTriage` y `triageops-gitops`).
- Complejidad adicional al gestionar tokens con permisos acotados (`GITOPS_TOKEN`) entre repositorios.
