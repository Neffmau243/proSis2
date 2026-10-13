"""ORM models for the stable clinical and administrative catalog tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CHAR, Boolean, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import MYSQL_TABLE_OPTIONS, Base

if TYPE_CHECKING:
    from .clinical import Attention, AttentionDiagnosis, AttentionService
    from .documents import CertificateService
    from .organization import Office
    from .patient import Patient, PatientResponsible
    from .security import Professional, ProfessionalSpecialty


class Ethnicity(Base):
    __tablename__ = "etnias"

    codigo: Mapped[str] = mapped_column(
        mysql.VARCHAR(2, charset="utf8mb4", collation="utf8mb4_unicode_ci"), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    fuente: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class DocumentType(Base):
    __tablename__ = "tipos_documento"

    codigo: Mapped[str] = mapped_column(String(10), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    pacientes: Mapped[list[Patient]] = relationship(back_populates="document_type")
    responsables: Mapped[list[PatientResponsible]] = relationship(back_populates="document_type")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class Sex(Base):
    __tablename__ = "sexos"

    codigo: Mapped[str] = mapped_column(CHAR(1), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    pacientes: Mapped[list[Patient]] = relationship(back_populates="sex")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class FamilyHistoryPrefix(Base):
    """Prefix used to compose a family-history identifier (for example AM-0012)."""

    __tablename__ = "historias_familiares_catalogo"

    codigo: Mapped[str] = mapped_column(String(4), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    color_hex: Mapped[str | None] = mapped_column(CHAR(7), nullable=True)
    orden: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    __table_args__ = (
        UniqueConstraint("orden", name="uq_historias_familiares_catalogo_orden"),
        MYSQL_TABLE_OPTIONS,
    )


class Insurance(Base):
    __tablename__ = "seguros"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Código del catálogo SIS de origen (``EESS_SIS``); NULL si no aplica.
    codigo_sis: Mapped[str | None] = mapped_column(String(10), nullable=True)
    #: SIS / ESSALUD / SANIDAD / PARTICULAR / NINGUNO / OTRO.
    regimen: Mapped[str | None] = mapped_column(String(20), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    pacientes: Mapped[list[Patient]] = relationship(back_populates="insurance")

    __table_args__ = (
        UniqueConstraint("codigo", name="uq_seguros_codigo"),
        UniqueConstraint("nombre", name="uq_seguros_nombre"),
        MYSQL_TABLE_OPTIONS,
    )


class Profession(Base):
    __tablename__ = "profesiones"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    profesionales: Mapped[list[Professional]] = relationship(back_populates="profesion")

    __table_args__ = (
        UniqueConstraint("nombre", name="uq_profesiones_nombre"),
        MYSQL_TABLE_OPTIONS,
    )


class Specialty(Base):
    __tablename__ = "especialidades"

    codigo: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    grupo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    profesionales_especialidad: Mapped[list[ProfessionalSpecialty]] = relationship(
        back_populates="especialidad"
    )
    consultorios: Mapped[list[Office]] = relationship(
        back_populates="especialidad", foreign_keys="Office.especialidad_codigo"
    )
    atenciones: Mapped[list[Attention]] = relationship(back_populates="especialidad")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class ServiceOffering(Base):
    __tablename__ = "prestaciones"

    codigo: Mapped[str] = mapped_column(String(30), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(300), nullable=False)
    grupo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    atenciones_prestacion: Mapped[list[AttentionService]] = relationship(
        back_populates="prestacion"
    )
    certificados_prestacion: Mapped[list[CertificateService]] = relationship(
        back_populates="prestacion"
    )

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class Cie10(Base):
    __tablename__ = "cie10"

    codigo: Mapped[str] = mapped_column(String(20), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(500), nullable=False)
    categoria: Mapped[str | None] = mapped_column(String(200), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    atenciones_diagnostico: Mapped[list[AttentionDiagnosis]] = relationship(back_populates="cie10")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class AttentionMode(Base):
    __tablename__ = "modalidades_atencion"

    codigo: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    atenciones: Mapped[list[Attention]] = relationship(back_populates="modalidad_atencion")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class AgeGroup(Base):
    __tablename__ = "grupos_etarios"

    codigo: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    edad_minima_meses: Mapped[int | None] = mapped_column(
        mysql.SMALLINT(unsigned=True), nullable=True
    )
    edad_maxima_meses: Mapped[int | None] = mapped_column(
        mysql.SMALLINT(unsigned=True), nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    atenciones: Mapped[list[Attention]] = relationship(back_populates="grupo_etario")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)
