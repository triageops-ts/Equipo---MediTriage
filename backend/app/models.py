"""Modelos SQLAlchemy de paciente y consentimiento (Tarjeta S04-2).

Reflejan las tablas que ya existen en Neon (nombres y tipos tal cual están allá).
Los campos marcados como "cifrado" son bytea: la app los cifra con pgcrypto usando
APP_ENCRYPTION_KEY antes de guardarlos (ver db.py). La clasificación PII completa
está en docs/data/clasificacion_pii.md.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class Paciente(Base):
    __tablename__ = "paciente"

    paciente_id: Mapped[uuid.UUID] = _uuid_pk()
    nombre_completo: Mapped[str | None] = mapped_column(String)  # PII, en claro hoy
    rut: Mapped[bytes | None] = mapped_column(LargeBinary)  # PII, cifrado
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date)  # PII (cuasi-identificador)
    sexo_biologico: Mapped[str | None] = mapped_column(String)  # clínico

    consentimientos: Mapped[list["Consentimiento"]] = relationship(back_populates="paciente")
    contacto: Mapped["ContactoPaciente | None"] = relationship(back_populates="paciente")
    contactos_emergencia: Mapped[list["ContactoEmergencia"]] = relationship(
        back_populates="paciente"
    )


class Consentimiento(Base):
    """Historial append-only: revocar un consentimiento = insertar otra fila con otorgado=false."""

    __tablename__ = "consentimiento"

    consentimiento_id: Mapped[uuid.UUID] = _uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paciente.paciente_id"), nullable=False
    )
    tipo_consentimiento: Mapped[str] = mapped_column(String, nullable=False)
    otorgado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("now()")
    )
    firma_digital: Mapped[bytes | None] = mapped_column(LargeBinary)  # sensible, cifrado
    version_texto: Mapped[str] = mapped_column(String, nullable=False)

    paciente: Mapped[Paciente] = relationship(back_populates="consentimientos")


class ContactoPaciente(Base):
    __tablename__ = "contacto_paciente"

    paciente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paciente.paciente_id"), primary_key=True
    )
    direccion: Mapped[bytes | None] = mapped_column(LargeBinary)  # PII, cifrado
    telefono: Mapped[bytes | None] = mapped_column(LargeBinary)  # PII, cifrado
    email: Mapped[bytes | None] = mapped_column(LargeBinary)  # PII, cifrado

    paciente: Mapped[Paciente] = relationship(back_populates="contacto")


class ContactoEmergencia(Base):
    __tablename__ = "contacto_emergencia"

    contacto_id: Mapped[uuid.UUID] = _uuid_pk()
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paciente.paciente_id"), nullable=False
    )
    nombre: Mapped[str | None] = mapped_column(String)  # PII, en claro hoy
    telefono: Mapped[str | None] = mapped_column(String)  # PII, en claro hoy
    relacion: Mapped[str | None] = mapped_column(String)

    paciente: Mapped[Paciente] = relationship(back_populates="contactos_emergencia")
