"""Esquemas de autenticación (LoginInput / LoginResponse de api/openapi.yaml)."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("Debe ser un correo electrónico válido.")
        return v


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    usuario_id: UUID
    rol: Literal["enfermero", "medico", "auditor"]


class SesionResponse(BaseModel):
    usuario_id: UUID
    rol: Literal["enfermero", "medico", "auditor"]
