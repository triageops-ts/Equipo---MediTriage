"""Pruebas de los modelos de paciente y consentimiento (S04-2). No necesitan base de datos:
revisan la estructura que SQLAlchemy construye al importar los modelos."""
from sqlalchemy import LargeBinary

from app.models import Base, Consentimiento, ContactoEmergencia, ContactoPaciente, Paciente


def test_tablas_declaradas():
    esperadas = {"paciente", "consentimiento", "contacto_paciente", "contacto_emergencia"}
    assert esperadas <= set(Base.metadata.tables)


def test_campos_pii_cifrados_son_bytea():
    assert isinstance(Paciente.__table__.c.rut.type, LargeBinary)
    for campo in ("direccion", "telefono", "email"):
        assert isinstance(ContactoPaciente.__table__.c[campo].type, LargeBinary)


def test_consentimiento_campos_obligatorios():
    columnas = Consentimiento.__table__.c
    for campo in ("paciente_id", "tipo_consentimiento", "otorgado", "fecha_hora", "version_texto"):
        assert columnas[campo].nullable is False


def test_claves_foraneas_apuntan_a_paciente():
    for modelo in (Consentimiento, ContactoPaciente, ContactoEmergencia):
        destinos = {fk.target_fullname for fk in modelo.__table__.foreign_keys}
        assert "paciente.paciente_id" in destinos


def test_relaciones_entre_modelos():
    assert Paciente.consentimientos.property.mapper.class_ is Consentimiento
    assert Paciente.contactos_emergencia.property.mapper.class_ is ContactoEmergencia
