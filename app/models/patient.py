"""ORM models for patients and their longitudinal registration data."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CHAR,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, MYSQL_TABLE_OPTIONS

if TYPE_CHECKING:
    from .catalog import DocumentType, Insurance, Sex
    from .clinical import Attention
    from .organization import Establishment, Localidad, Ubigeo
    from .surveillance import NutritionalEvaluation, SurveillanceSien


class Patient(Base):
    __tablename__ = "pacientes"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    codclie_legacy: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True), nullable=True
    )
    historia_clinica: Mapped[str | None] = mapped_column(String(255), nullable=True)
    historia_familiar: Mapped[str | None] = mapped_column(Text, nullable=True)
    sis_diresa: Mapped[str | None] = mapped_column(String(3), nullable=True)
    sis_tipo: Mapped[str | None] = mapped_column(String(2), nullable=True)
    sis_numero: Mapped[str | None] = mapped_column(String(9), nullable=True)
    sis_secuencia: Mapped[str | None] = mapped_column(String(2), nullable=True)
    etnia_codigo: Mapped[str | None] = mapped_column(
        mysql.VARCHAR(2, charset="utf8mb4", collation="utf8mb4_unicode_ci"),
        ForeignKey("etnias.codigo", name="fk_pacientes_etnia", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    tipo_documento_codigo: Mapped[str] = mapped_column(
        String(10),
        ForeignKey(
            "tipos_documento.codigo",
            name="fk_pacientes_tipo_documento",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    numero_documento: Mapped[str] = mapped_column(String(30), nullable=False)
    sufijo_documento: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha_inscripcion: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    apellido_paterno: Mapped[str | None] = mapped_column(String(100), nullable=True)
    apellido_materno: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primer_nombre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    otros_nombres: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sexo_codigo: Mapped[str | None] = mapped_column(
        CHAR(1),
        ForeignKey(
            "sexos.codigo",
            name="fk_pacientes_sexo",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    ubigeo_residencia_codigo: Mapped[str | None] = mapped_column(
        CHAR(6),
        ForeignKey(
            "ubigeos.codigo",
            name="fk_pacientes_ubigeo",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    localidad: Mapped[str | None] = mapped_column(String(150), nullable=True)
    localidad_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "localidades.id",
            name="fk_pacientes_localidad",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    direccion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    establecimiento_registro_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "establecimientos.id",
            name="fk_pacientes_establecimiento",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    profesional_registro_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "profesionales.id",
            name="fk_pacientes_profesional_registro",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    seguro_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "seguros.id",
            name="fk_pacientes_seguro",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    telefono_principal: Mapped[str | None] = mapped_column(String(30), nullable=True)
    condicion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    document_type: Mapped["DocumentType"] = relationship(back_populates="pacientes")
    sex: Mapped["Sex | None"] = relationship(back_populates="pacientes")
    insurance: Mapped["Insurance | None"] = relationship(back_populates="pacientes")
    ubigeo_residencia: Mapped["Ubigeo | None"] = relationship(
        back_populates="pacientes"
    )
    localidad_catalogo: Mapped["Localidad | None"] = relationship(
        back_populates="pacientes"
    )
    establecimiento_registro: Mapped["Establishment | None"] = relationship(
        back_populates="pacientes_registrados"
    )
    riesgos: Mapped[list["PatientRisk"]] = relationship(back_populates="paciente")
    responsables: Mapped[list["PatientResponsible"]] = relationship(
        back_populates="paciente"
    )
    codigos_externos: Mapped[list["PatientExternalCode"]] = relationship(
        back_populates="paciente"
    )
    anexos_legacy: Mapped[list["PatientLegacyAnnex"]] = relationship(
        back_populates="paciente"
    )
    atenciones: Mapped[list["Attention"]] = relationship(back_populates="paciente")
    vigilancia_sien: Mapped[list["SurveillanceSien"]] = relationship(
        back_populates="paciente"
    )
    evaluaciones_nutricionales: Mapped[list["NutritionalEvaluation"]] = relationship(
        back_populates="paciente"
    )

    __table_args__ = (
        UniqueConstraint("codclie_legacy", name="uq_pacientes_codclie_legacy"),
        UniqueConstraint(
            "tipo_documento_codigo",
            "numero_documento",
            name="uq_pacientes_documento",
        ),
        Index("idx_pacientes_historia", "historia_clinica"),
        Index(
            "idx_pacientes_nombres",
            "apellido_paterno",
            "apellido_materno",
            "primer_nombre",
        ),
        Index("idx_pacientes_profesional_registro", "profesional_registro_id"),
        MYSQL_TABLE_OPTIONS,
    )


class RiskGroup(Base):
    __tablename__ = "grupos_riesgo"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )

    riesgos_paciente: Mapped[list["PatientRisk"]] = relationship(
        back_populates="grupo_riesgo"
    )

    __table_args__ = (
        UniqueConstraint("codigo", name="uq_grupos_riesgo_codigo"),
        MYSQL_TABLE_OPTIONS,
    )


class PatientRisk(Base):
    __tablename__ = "paciente_grupos_riesgo"

    paciente_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "pacientes.id",
            name="fk_paciente_grupo_riesgo_paciente",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    grupo_riesgo_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "grupos_riesgo.id",
            name="fk_paciente_grupo_riesgo_grupo",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    fecha_inicio: Mapped[date] = mapped_column(Date, primary_key=True)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)

    atencion_origen_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True), ForeignKey("atenciones.id", name="fk_riesgo_atencion"),
        nullable=True,
    )
    evaluacion_origen: Mapped[dict | None] = mapped_column(mysql.JSON, nullable=True)
    confirmado_por_usuario_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True), ForeignKey("usuarios.id", name="fk_riesgo_confirmador"),
        nullable=True,
    )
    fecha_proximo_control: Mapped[date | None] = mapped_column(Date, nullable=True)
    motivo_cierre: Mapped[str | None] = mapped_column(String(500), nullable=True)

    paciente: Mapped["Patient"] = relationship(back_populates="riesgos")
    grupo_riesgo: Mapped["RiskGroup"] = relationship(back_populates="riesgos_paciente")

    __table_args__ = (
        Index("idx_paciente_grupos_riesgo_activos", "paciente_id", "fecha_fin"),
        MYSQL_TABLE_OPTIONS,
    )


class PatientResponsible(Base):
    __tablename__ = "paciente_responsables"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    paciente_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "pacientes.id",
            name="fk_paciente_responsables_paciente",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    parentesco: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo_documento_codigo: Mapped[str | None] = mapped_column(
        String(10),
        ForeignKey(
            "tipos_documento.codigo",
            name="fk_paciente_responsables_tipo_documento",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    numero_documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    es_principal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )

    paciente: Mapped["Patient"] = relationship(back_populates="responsables")
    document_type: Mapped["DocumentType | None"] = relationship(
        back_populates="responsables"
    )

    __table_args__ = (
        Index("idx_paciente_responsables_paciente", "paciente_id", "activo"),
        MYSQL_TABLE_OPTIONS,
    )


class PatientExternalCode(Base):
    __tablename__ = "paciente_codigos_externos"

    paciente_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "pacientes.id",
            name="fk_paciente_codigos_paciente",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    sistema: Mapped[str] = mapped_column(String(40), primary_key=True)
    valor: Mapped[str] = mapped_column(String(255), nullable=False)

    paciente: Mapped["Patient"] = relationship(back_populates="codigos_externos")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class PatientLegacyAnnex(Base):
    __tablename__ = "paciente_anexos_legacy"

    paciente_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "pacientes.id",
            name="fk_anexos_legacy_paciente",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    numero_anexo: Mapped[int] = mapped_column(
        mysql.TINYINT(unsigned=True), primary_key=True
    )
    tipo_origen: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'TEXTO'")
    )
    valor_texto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valor_booleano: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    paciente: Mapped["Patient"] = relationship(back_populates="anexos_legacy")

    __table_args__ = (MYSQL_TABLE_OPTIONS,)
