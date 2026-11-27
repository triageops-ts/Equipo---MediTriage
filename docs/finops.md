# FinOps — MediTriage (S12-14)

## 1. Objetivo

Identificar los costos asociados a la infraestructura de
MediTriage, establecer etiquetas de identificación de
recursos y analizar alternativas de optimización que
permitan reducir el consumo de recursos y controlar
los gastos operacionales del proyecto.

## 2. Inventario de infraestructura

El ambiente de staging funciona sobre una máquina
virtual de Azure for Students, ubicada en la región
North Central US, utilizando Kubernetes (k3s) y Argo CD.

| Recurso | Configuración | Fuente interna |
|---|---|---|
| Azure VM | North Central US | README.md |
| Backend | 2 réplicas, HPA de 2 a 10 | k8s/deployment.yaml |
| Frontend | 2 réplicas | k8s/frontend-deployment.yaml |
| PostgreSQL | Neon, branch staging | README.md |
| Redis | 1 réplica en Kubernetes | docs/dr-plan.md |
| Registro de imágenes | GHCR | docs/dr-plan.md |
| Motor de IA | fallback-rule-engine | docs/ia/evaluacion.md |
| Acceso externo | ngrok gratuito | README.md |
| Namespace | Gestionado por Terraform | terraform/main.tf |
| Secret | Gestionado por Terraform | terraform/main.tf |

Terraform administra recursos Kubernetes y no
aprovisiona directamente la máquina virtual de Azure.

El backend remoto S3 se encuentra comentado,
por lo que no se considera un recurso activo.

## 3. Estimación de costos mensuales

Moneda: USD.
Periodo de referencia: 730 horas mensuales.
Fecha de consulta de precios: 27-11-2026.

| Recurso | Costo mensual | Observación |
|---|---:|---|
| Azure VM | Pendiente de confirmar | Depende del SKU y horas facturables |
| Disco e IP de Azure | Pendiente de confirmar | Depende de la configuración |
| Kubernetes y Argo CD | USD 0 adicionales | Incluidos en la VM |
| Backend y frontend | USD 0 adicionales | Incluidos en la VM |
| PostgreSQL Neon | USD 0 si utiliza Free | Plan real no confirmado |
| Redis | USD 0 adicionales | Incluido en la VM |
| GHCR | USD 0 | Almacenamiento y transferencia de imágenes gratuitos |
| Motor de reglas | USD 0 adicionales | Sin llamadas a Claude |
| ngrok | USD 0 | Plan gratuito |
| Namespace y Secret | USD 0 adicionales | Recursos internos de Kubernetes |

### 3.1. Escenario presupuestario

El tamaño real de la VM no está registrado en los
documentos revisados.

Como escenario de planificación, si se considera
una tarifa hipotética de USD 0,04 por hora:

730 horas x USD 0,04 = USD 29,20 mensuales.

Este valor representa exclusivamente un ejemplo
presupuestario de cómputo, no una tarifa verificada
para la instancia real del proyecto.

El costo total deberá incorporar disco, red y posibles
servicios de pago cuando se confirme su configuración.

Los créditos educativos de Azure permiten financiar
el consumo, pero no eliminan el costo de los recursos.

### 3.2. Fuentes oficiales de precios

Consultadas el 27-11-2026:

- Azure Virtual Machines:
  https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/

- Azure Managed Disks:
  https://azure.microsoft.com/en-us/pricing/details/managed-disks/

- Neon:
  https://neon.com/pricing

- GitHub Container Registry:
  https://docs.github.com/en/billing/concepts/product-billing/github-packages

- ngrok:
  https://ngrok.com/pricing

- Anthropic:
  https://platform.claude.com/docs/en/about-claude/pricing

## 4. Etiquetado de recursos

Se incorporaron etiquetas comunes en terraform/main.tf
mediante metadata.labels.

| Etiqueta | Valor | Finalidad |
|---|---|---|
| proyecto | meditriage | Identificar el proyecto |
| ambiente | local | Identificar el entorno predeterminado |
| responsable | triageops | Identificar al equipo responsable |

El ambiente es configurable mediante una variable
Terraform y puede establecerse como staging cuando
corresponda.

Las etiquetas se incorporaron en:

- kubernetes_namespace.equipo_ns
- kubernetes_secret.placeholder_secret

Estas etiquetas permiten identificar los recursos de
Kubernetes. No equivalen a etiquetas de facturación
aplicadas directamente a la VM de Azure.

Commit: 0fcc4cc.

La validación de Checkov se realizará mediante el
pipeline de seguridad del Pull Request.

## 5. Palancas de optimización

### 5.1. Palanca 1: escalado automático mediante HPA

Se utilizaron las evidencias de carga existentes
en el repositorio de MediTriage.

Configuración:

- Réplicas mínimas: 2.
- Réplicas máximas: 10.
- Utilización objetivo de CPU: 50 %.
- CPU solicitada por réplica: 250m.
- Memoria solicitada por réplica: 256 MiB.

| Indicador | Durante la carga | Después de la carga |
|---|---:|---:|
| Réplicas activas | 8 | 2 |
| Utilización de CPU | 46 % | 1 % |
| CPU solicitada total | 2000m | 500m |
| Memoria solicitada total | 2048 MiB | 512 MiB |
| Reinicios registrados | 0 | 0 |

Resultados:

- Reducción de 6 réplicas activas.
- Reducción del 75 % de las réplicas.
- Liberación de 1500m de CPU solicitada.
- Liberación de 1536 MiB de memoria solicitada.
- Disminución de la utilización reportada de CPU
  en 45 puntos porcentuales.

El HPA permite aumentar la capacidad durante la
demanda y regresar al mínimo configurado cuando
disminuye la carga.

Las réplicas y porcentajes de CPU fueron observados
en las evidencias originales. La CPU y memoria
solicitadas se calcularon desde el manifiesto.

La reducción de recursos no implica automáticamente
una disminución del 75 % en la factura de Azure,
debido a que la VM mantiene su capacidad contratada.

Evidencias:

- docs/data/evidencia-hpa/02-durante.txt
- docs/data/evidencia-hpa/03-despues.txt
- k8s/hpa.yaml
- k8s/deployment.yaml

### 5.2. Palanca 2: motor de respaldo por reglas

Para la demostración final se utiliza el motor
fallback-rule-engine, debido a que el proyecto
no dispone de ANTHROPIC_API_KEY.

Mediciones de la tarjeta S12-2:

| Indicador | Claude | Respaldo por reglas |
|---|---|---|
| Evaluaciones medidas | No disponible | 5 |
| Latencia del motor | No medida | 0 a 3 ms |
| Latencia total | No medida | 66 a 138 ms |
| Tokens facturables | No medidos | 0 |
| Costo directo de API | Depende del consumo | USD 0 |

La tarjeta S12-15 también evaluó el respaldo
mediante un golden set de 15 casos sintéticos.

| Indicador | Resultado |
|---|---:|
| Evaluaciones | 15 |
| Acierto exacto | 80 % |
| Acierto a un nivel de diferencia | 100 % |
| Subclasificaciones | 0 |
| Sobreclasificaciones | 3 |
| Respuestas del respaldo | 15/15 |
| Latencia reportada del motor | 0 ms |

Estos resultados corresponden a una muestra técnica
pequeña y no constituyen validación clínica.

#### Comparación económica referencial

Para Claude Haiku 5.5, la tarifa publicada para
prompts de hasta 100.000 tokens es:

- Entrada: USD 0,10 por millón de tokens.
- Salida: USD 0,50 por millón de tokens.

Escenario hipotético de 10.000 evaluaciones mensuales,
con 2.000 tokens de entrada y 300 de salida por evaluación:

- Tokens de entrada: 20.000.000.
- Tokens de salida: 3.000.000.
- Costo de entrada: USD 2,00.
- Costo de salida: USD 1,50.

| Indicador | Claude estimado | Respaldo |
|---|---:|---:|
| Evaluaciones del escenario | 10.000 | 10.000 |
| Costo directo de API | USD 3,50 | USD 0 |
| Ahorro potencial de API | - | USD 3,50 |

El respaldo evita el 100 % del gasto directo de API
en este escenario hipotético.

Los volúmenes de tokens son supuestos presupuestarios
y no mediciones reales del proyecto.

La comparación experimental antes y después queda
pendiente hasta disponer de una clave de Anthropic.

Evidencias:

- Tarjeta S12-2.
- docs/ia/evaluacion.md.
- docs/data/auditoria-payload-ia.md.

## 6. Recomendaciones

- Mantener el HPA para ajustar la capacidad a la demanda.
- Utilizar el respaldo por reglas en la demo final.
- Revisar periódicamente el consumo de créditos Azure.
- Confirmar el SKU de la VM y el plan contratado en Neon.
- Evaluar la desasignación de la VM fuera de periodos de
  uso, previa coordinación con el equipo.
- Medir el consumo real de tokens cuando Claude esté
  disponible.
- Mantener las etiquetas en los recursos futuros.

## 7. Conclusión

MediTriage utiliza una infraestructura que combina
servicios gratuitos, recursos compartidos y créditos
educativos, permitiendo controlar los costos del MVP.

Las evidencias del HPA muestran una reducción del
75 % de las réplicas activas después de la carga.
El motor de respaldo permite realizar evaluaciones
sin generar gastos directos en la API de Claude.

Se incorporó un esquema de etiquetado para identificar
los recursos gestionados por Terraform.

Queda pendiente confirmar el costo exacto de Azure,
el plan de Neon, la comparación experimental con Claude
y el resultado de Checkov.
