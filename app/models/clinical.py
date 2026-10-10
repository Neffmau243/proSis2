"""ORM models for clinical encounters and their ordered details."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, MYSQL_TABLE_OPTIONS

if TYPE_CHECKING:
    from .catalog import AgeGroup, AttentionMode, Cie10, ServiceOffering, Specialty
    from .documents import Certificate, Fua, Referral
    from .organization import Establishment, Office
    from .patient import Patient
    from .security import Professional, User
    from .surveillance import NutritionalEvaluation, SurveillanceSien


class Attention(Base):
    __tablename__ = "atenciones"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    codigo_legacy: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True), nullable=True
    )
    paciente_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "pacientes.id",
            name="fk_atenciones_paciente",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    establecimiento_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "establecimientos.id",
            name="fk_atenciones_establecimiento",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    profesional_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "profesionales.id",
            name="fk_atenciones_profesional",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    especialidad_codigo: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey(
            "especialidades.codigo",
            name="fk_atenciones_especialidad",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    consultorio_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "consultorios.id",
            name="fk_atenciones_consultorio",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    modalidad_atencion_codigo: Mapped[str] = mapped_column(
        String(20),
        ForeignKey(
            "modalidades_atencion.codigo",
            name="fk_atenciones_modalidad",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    grupo_etario_codigo: Mapped[str] = mapped_column(
        String(20),
        ForeignKey(
            "grupos_etarios.codigo",
            name="fk_atenciones_grupo_etario",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    grupo_atencion_codigo: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default=text("'NINOS_ADOLESCENTES_ADULTOS_MAYORES'"),
    )
    fecha_atencion: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fecha_atendido: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    historia_clinica_snapshot: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    edad_anios: Mapped[int | None] = mapped_column(
        mysql.SMALLINT(unsigned=True), nullable=True
    )
    peso_kg: Mapped[Decimal | None] = mapped_column(
        mysql.DECIMAL(6, 2), nullable=True
    )
    talla_cm: Mapped[Decimal | None] = mapped_column(
        mysql.DECIMAL(6, 2), nullable=True
    )
    perimetro_abdominal_cm: Mapped[Decimal | None] = mapped_column(
        mysql.DECIMAL(6, 2), nullable=True
    )
    tipo_embarazo_codigo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    peso_antes_embarazo_kg: Mapped[Decimal | None] = mapped_column(
        mysql.DECIMAL(6, 2), nullable=True
    )
    fecha_probable_parto: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Fecha real del parto, exclusiva de las atenciones de PUERPERAS.
    fecha_parto: Mapped[date | None] = mapped_column(Date, nullable=True)
    presion_sistolica: Mapped[int | None] = mapped_column(
        mysql.SMALLINT(unsigned=True), nullable=True
    )
    presion_diastolica: Mapped[int | None] = mapped_column(
        mysql.SMALLINT(unsigned=True), nullable=True
    )
    temperatura_c: Mapped[Decimal | None] = mapped_column(
        mysql.DECIMAL(4, 1), nullable=True
    )
    imc: Mapped[Decimal | None] = mapped_column(mysql.DECIMAL(6, 3), nullable=True)
    pe: Mapped[str | None] = mapped_column(String(50), nullable=True)
    te: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pt: Mapped[str | None] = mapped_column(String(50), nullable=True)
    referencia_nutricional: Mapped[str | None] = mapped_column(String(80), nullable=True)
    valoracion_calculada: Mapped[dict | None] = mapped_column(mysql.JSON, nullable=True)
    contexto_clinico: Mapped[dict | None] = mapped_column(mysql.JSON, nullable=True)
    hora_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)
    hora_fin: Mapped[time | None] = mapped_column(Time, nullable=True)
    admision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    fua_impresion: Mapped[dict | None] = mapped_column(mysql.JSON, nullable=True)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'ATENDIDO'")
    )
    created_by_usuario_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "usuarios.id",
            name="fk_atenciones_creado_por",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
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

    paciente: Mapped["Patient"] = relationship(back_populates="atenciones")
    establecimiento: Mapped["Establishment"] = relationship(back_populates="atenciones")
    profesional: Mapped["Professional"] = relationship(back_populates="atenciones")
    especialidad: Mapped["Specialty | None"] = relationship(back_populates="atenciones")
    consultorio: Mapped["Office"] = relationship(back_populates="atenciones")
    modalidad_atencion: Mapped["AttentionMode"] = relationship(
        back_populates="atenciones"
    )
    grupo_etario: Mapped["AgeGroup"] = relationship(back_populates="atenciones")
    created_by_usuario: Mapped["User | None"] = relationship(
        back_populates="atenciones_creadas"
    )
    prestaciones: Mapped[list["AttentionService"]] = relationship(
        back_populates="atencion", order_by="AttentionService.numero_orden"
    )
    diagnosticos: Mapped[list["AttentionDiagnosis"]] = relationship(
        back_populates="atencion", order_by="AttentionDiagnosis.numero_orden"
    )
    referencias: Mapped[list["Referral"]] = relationship(back_populates="atencion")
    fua: Mapped["Fua | None"] = relationship(back_populates="atencion", uselist=False)
    certificados: Mapped[list["Certificate"]] = relationship(
        back_populates="atencion",
        overlaps="profesional",
    )
    vigilancia_sien: Mapped[list["SurveillanceSien"]] = relationship(
        back_populates="atencion"
    )
    evaluaciones_nutricionales: Mapped[list["NutritionalEvaluation"]] = relationship(
        back_populates="atencion"
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('ATENDIDO', 'ANULADO')",
            name="ck_atenciones_estado_valido",
        ),
        CheckConstraint(
            "grupo_atencion_codigo IN ("
            "'NINOS_ADOLESCENTES_ADULTOS_MAYORES', 'GESTANTES', 'PUERPERAS'"
            ")",
            name="ck_atenciones_grupo_atencion_valido",
        ),
        CheckConstraint(
            "tipo_embarazo_codigo IS NULL "
            "OR tipo_embarazo_codigo IN ('UNICO', 'MULTIPLE')",
            name="ck_atenciones_tipo_embarazo_valido",
        ),
        UniqueConstraint("codigo_legacy", name="uq_atenciones_codigo_legacy"),
        UniqueConstraint(
            "id",
            "profesional_id",
            name="uq_atenciones_id_profesional",
        ),
        Index("idx_atenciones_paciente_fecha", "paciente_id", "fecha_atencion"),
        Index(
            "idx_atenciones_establecimiento_fecha",
            "establecimiento_id",
            "fecha_atencion",
        ),
        Index(
            "idx_atenciones_profesional_fecha", "profesional_id", "fecha_atencion"
        ),
        MYSQL_TABLE_OPTIONS,
    )


class AttentionService(Base):
    __tablename__ = "atencion_prestaciones"

    atencion_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "atenciones.id",
            name="fk_atencion_prestaciones_atencion",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    numero_orden: Mapped[int] = mapped_column(
        mysql.SMALLINT(unsigned=True), primary_key=True
    )
    prestacion_codigo: Mapped[str] = mapped_column(
        String(30),
        ForeignKey(
            "prestaciones.codigo",
            name="fk_atencion_prestaciones_prestacion",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    cantidad: Mapped[Decimal] = mapped_column(
        mysql.DECIMAL(8, 2), nullable=False, server_default=text("1")
    )

    atencion: Mapped["Attention"] = relationship(back_populates="prestaciones")
    prestacion: Mapped["ServiceOffering"] = relationship(
        "ServiceOffering", back_populates="atenciones_prestacion"
    )

    __table_args__ = (
        Index("idx_atencion_prestaciones_codigo", "prestacion_codigo"),
        MYSQL_TABLE_OPTIONS,
    )


class AttentionDiagnosis(Base):
    __tablename__ = "atencion_diagnosticos"

    atencion_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "atenciones.id",
            name="fk_atencion_diagnosticos_atencion",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    numero_orden: Mapped[int] = mapped_column(
        mysql.SMALLINT(unsigned=True), primary_key=True
    )
    cie10_codigo: Mapped[str] = mapped_column(
        String(20),
        ForeignKey(
            "cie10.codigo",
            name="fk_atencion_diagnosticos_cie10",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    tipo_diagnostico: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observacion: Mapped[str | None] = mapped_column(String(500), nullable=True)

    atencion: Mapped["Attention"] = relationship(back_populates="diagnosticos")
    cie10: Mapped["Cie10"] = relationship(
        "Cie10", back_populates="atenciones_diagnostico"
    )

    __table_args__ = (
        Index("idx_atencion_diagnosticos_cie10", "cie10_codigo"),
        MYSQL_TABLE_OPTIONS,
    )
