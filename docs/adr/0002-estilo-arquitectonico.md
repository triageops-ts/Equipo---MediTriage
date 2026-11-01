# ADR 0002 - Estilo arquitectonico elegido: Monolito modular (arquitectura en capas)
---
## Fecha
03/09/26

## Autores
Josefa Rodriguez, Lucas Benítez, Marcela Contreras, Isidora Ramos, Antonia Moya y Kimberlly Guillén

---
## 1. Contexto y Problema

Para el desarrollo del proyecto MediTriage, debemos elegir un estilo arquitectónico que equilibre los requisitos de calidad del sistema con las restricciones de desarrollo del equipo.

El sistema cuenta con requisitos críticos de calidad como:

- Una latencia de <3s
- Disponibilidad 99:.5%
- Restricción de proyecto: Plazo limitado

---
## 2. Decisiones Consideradas

### Opción A: Arquitectura de Microservicios
**Ventajas:** Alta disponibilidad por aislamiento de fallas, excelente escalabilidad futura y aislamiento del motor de IA para pruebas e inspección independientes.
**Desventajas:** Alta complejidad en despliegue, configuración e infraestructura. Incrementa el riesgo de latencia debido a los múltiples saltos de red entre servicios (lo que exige esfuerzo y tiempo considerable para optimizar).

### Opción B: Arquitectura en Capas / Monolito Modular (Elegida)
**Ventajas:** Desarrollo más rápido y de menor complejidad. Llamadas internas entre módulos que eliminan la latencia de red (favoreciendo directamente la restricción de respuesta menor a 3 segundos). Un único perímetro de seguridad y centralización de la lógica del negocio.
**Desventajas:** Punto único de falla (requiere monitoreo para cuidar la disponibilidad) y mayor acoplamiento si no se respeta la separación estricta de capas.

---
## 3. Decisión final

Elegimos implementar una **Arquitectura en Capas (Monolito Modular)** para el desarrollo de MediTriage.

---
## 4. Justificacion de la decisión

Si bien la arquitectura de microservicios tenia puntos muy buenos, la carga operativa de orquestar servicios, configurar redes e implementar seguridad granular requeriría un esfuerzo y tiempo significativos, al elegir una arquitectura en capas, reducimos la complejidad de desarrollo y podemos enfocar ese tiempo en mejorar otros aspectos fundamentales del proyecto (como el desarrollo de funcionalidades y la lógica del negocio), tambien al procesar los componentes del sistema dentro de una misma unidad de despliegue, las llamadas entre la lógica de negocio, el motor de IA y los datos son internas, esto elimina los retardos generados por las peticiones de red entre microservicios, asegurando una respuesta más ágil en la sala de urgencias.
Para el alcance de un producto mínimo viable (MVP) con un equipo reducido y tiempos acotados, la arquitectura en capas ofrece el equilibrio óptimo entre bajo costo de mantenimiento inicial y agilidad de entrega.

---
## 5. Consecuencias

**Positivas:**

* Reducción de la latencia en la elaboración de datos clínicos y creación de categorías ESI.
* Zona de seguridad centralizada para la gestión de información sensible de pacientes (PII).

**Negativas / Mitigaciones:**
**Riesgo:** Hay un único punto de fallo que podría afectar la disponibilidad del 99.5%.
**Mitigación:** Se establecerá una rigurosa modularidad interna por niveles para que, si es necesario trasladar ciertos módulos pesados (como el motor de IA) a servicios autónomos en el futuro, el desacoplamiento sea sencillo.
