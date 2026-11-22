Feature: Decisión clínica en triage (US-02)
  Como profesional de salud autorizado
  Quiero confirmar o modificar una decisión clínica asociada a un episodio de triage
  Para que el equipo tenga un ejemplo base de pruebas BDD con datos sintéticos

  Scenario: Modificar nivel ESI con justificación válida usando datos sintéticos
    Given un usuario con rol "enfermero" y un paciente sintético con consentimiento
    When se prepara una decisión clínica modificando el nivel ESI sugerido con justificación
    Then la decisión clínica cumple el contrato esperado de US-02
