# ADR 0005: Plataforma de despliegue: Kubernetes local (Docker Desktop) e IaC con Terraform

## Fecha
16/10/26

## Autores
Josefa Rodriguez, Lucas Benítez, Marcela Contreras, Isidora Ramos, Antonia Moya y Kimberlly Guillén

## Contexto
El ADR 0003 definió para MediTriage un monolito modular cloud-native empaquetado en una única imagen de Docker, pensada para desplegarse en servicios gestionados (AWS ECS Fargate o GCP Cloud Run). El mini-lab de esta sesión pide empaquetar y desplegar el servicio principal en Kubernetes, y definir parte de la infraestructura como código.

La pauta establece las siguientes restricciones:
- Un cluster local de Kubernetes (`kind`, `minikube` o `k3d`, o en este caso **Docker Desktop**), con Docker Desktop y `kubectl` instalados.
- Terraform ≥ 1.6 con el provider de Kubernetes.
- Manifiestos de Kubernetes aplicados con Kustomize (`kubectl apply -k`).
- Un HPA configurado y probado.

El alcance es el servicio principal (backend). PostgreSQL y Redis no se despliegan en este entorno.

## Decisión
Se toman dos decisiones:
1. **Cluster local:** Kubernetes integrado en Docker Desktop.
2. **Infraestructura como código:** Terraform con el provider de Kubernetes, que crea el namespace `triageops` y el secret `triageops-secrets` (con valores placeholder). Los manifiestos de la aplicación (Deployment, Service, ConfigMap, Ingress y HPA) se aplican con Kustomize.

Terraform es el único responsable de crear el namespace y el secret. Kustomize no define esos recursos, para evitar conflictos de administración entre ambas herramientas.

Kubernetes se usa como plataforma de este mini-lab y no reemplaza el destino de producción definido en el ADR 0003 y en `managed-services.md`.

## Razones de la decisión

### Cluster local: Docker Desktop
1. **Ya instalado y disponible:** Al ser un requisito obligatorio para el desarrollo, el clúster de Kubernetes nativo se activa directamente en las preferencias de Docker Desktop sin requerir la instalación de herramientas adicionales o binarios externos.
2. **Entorno unificado:** Permite gestionar tanto los contenedores como el clúster de Kubernetes desde la misma interfaz y motor de Docker que el equipo ya conoce y utiliza.
3. **Control estándar:** Ofrece un clúster limpio de nodo único con soporte completo para `kubectl` y despliegues estándar de manifiestos.

### Infraestructura como código: Terraform
1. **Lo exige la pauta del mini-lab.** Esta es la razón principal de la elección.
2. **Plan revisable antes de aplicar:** `terraform plan` mostró exactamente qué recursos se iban a crear (2) antes de ejecutar `apply`.
3. **Parametrizable y seguro:** el nombre del namespace se define con una variable, y el valor del secret se declara como variable sensible (`sensitive`), por lo que no se muestra en los registros.
4. **Versionado y reproducible:** la configuración vive en `terraform/main.tf` dentro del repositorio y se ejecuta con `init`, `plan` y `apply`.

### Reparto entre Terraform y Kustomize
Cada recurso tiene un único dueño: Terraform administra el namespace y el secret, y Kustomize administra los manifiestos de la aplicación. Así se evita que dos herramientas intenten crear o modificar el mismo recurso.

## Evidencia de verificación
- **Estado del despliegue (`kubectl get all -n triageops`):** Pods en estado Running, Deployment disponible, Service configurado y HPA operativo.
- **Prueba del HPA (`kubectl get hpa -w`):** Con la carga de la prueba, el HPA respondió correctamente escalando el número de réplicas según la demanda de CPU configurada, y desescalando al estabilizarse.
- **Terraform:** `apply` terminó con `Resources: 2 added, 0 changed, 0 destroyed` (namespace `triageops` y secret `triageops-secrets`).

Las capturas están en el README del repositorio.

## Alternativas descartadas
Las siguientes opciones no se evaluaron en la práctica. Se mencionan solo como referencia.

### Cluster local
- **k3d / kind / minikube:** Se descartaron ya que Docker Desktop ofrece una solución integrada que evita instalar dependencias adicionales en las máquinas del equipo.

### Infraestructura como código
- La pauta fijó Terraform, por lo que no se evaluaron otras herramientas. Como referencia, existen OpenTofu (compatible con Terraform) y Pulumi (infraestructura en lenguajes de programación).

### Despliegue sin Kubernetes
- AWS ECS Fargate y GCP Cloud Run (ADR 0003) se mantienen como destino de producción.

## Consecuencias

### Positivas
- Integración nativa aprovechando la herramienta de contenedores ya instalada (Docker Desktop).
- Autoescalado HPA y separación de responsabilidades validados exitosamente.
- Ninguna credencial real en el repositorio: el secret usa valores placeholder.

### Negativas
- El estado de Terraform es local. El backend remoto (S3) está declarado en `main.tf` pero desactivado por falta de credenciales, y no incluye configuración de bloqueo (locking). Esto implica riesgo de perder el estado y de conflictos si más de una persona ejecuta Terraform.
- El Kubernetes de Docker Desktop puede consumir más recursos de memoria en segundo plano en comparación con herramientas ligeras (*Edge*).
- Dos herramientas que mantener (Terraform y Kustomize).
- Alcance limitado: el entorno valida el empaquetado, el arranque y el escalado del servicio, pero no su comportamiento con PostgreSQL y Redis.
