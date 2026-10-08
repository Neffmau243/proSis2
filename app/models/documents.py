"""ORM models for referrals, FUA documents, and certificates."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
    from .catalog import ServiceOffering
    from .clinical import Attention
    from .organization import Establishment
    from .security import Professional


class Referral(Base):
    __tablename__ = "referencias"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    atencion_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "atenciones.id",
            name="fk_referencias_atencion",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    numero_referencia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    establecimiento_origen_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "establecimientos.id",
            name="fk_referencias_origen",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    establecimiento_destino_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "establecimientos.id",
            name="fk_referencias_destino",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    fecha_emision: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'PENDIENTE'")
    )

    atencion: Mapped["Attention"] = relationship(back_populates="referencias")
    establecimiento_origen: Mapped["Establishment"] = relationship(
        foreign_keys=[establecimiento_origen_id], back_populates="referencias_origen"
    )
    establecimiento_destino: Mapped["Establishment"] = relationship(
        foreign_keys=[establecimiento_destino_id],
        back_populates="referencias_destino",
    )

    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE', 'ACEPTADA', 'ATENDIDA', 'CONTRARREFERIDA', 'CERRADA', 'ANULADA')",
            name="ck_referencias_estado_valido",
        ),
        UniqueConstraint("numero_referencia", name="uq_referencias_numero"),
        Index("idx_referencias_atencion", "atencion_id"),
        Index(
            "idx_referencias_destino_estado", "establecimiento_destino_id", "estado"
        ),
        MYSQL_TABLE_OPTIONS,
    )


class Fua(Base):
    __tablename__ = "fua"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    atencion_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "atenciones.id",
            name="fk_fua_atencion",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    numero_fua: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # The components of the current SIS number are persisted independently so
    # that a printed/exported FUA can be traced without parsing presentation
    # text.  The older ``codigo_*`` fields are retained only for legacy rows.
    codigo_renipress: Mapped[str | None] = mapped_column(String(8), nullable=True)
    lote_fua: Mapped[str | None] = mapped_column(String(2), nullable=True)
    correlativo_fua: Mapped[str | None] = mapped_column(String(8), nullable=True)
    codigo_ciudad: Mapped[str | None] = mapped_column(String(50), nullable=True)
    codigo_anio: Mapped[str | None] = mapped_column(String(20), nullable=True)
    codigo_eess: Mapped[str | None] = mapped_column(String(50), nullable=True)
    edad_declarada: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fecha_emision: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'EMITIDO'")
    )
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    atencion: Mapped["Attention"] = relationship(back_populates="fua")

    __table_args__ = (
        CheckConstraint(
            "estado IN ('EMITIDO', 'ANULADO')",
            name="ck_fua_estado_valido",
        ),
        UniqueConstraint("atencion_id", name="uq_fua_atencion"),
        UniqueConstraint("numero_fua", name="uq_fua_numero"),
        Index("idx_fua_fecha_emision", "fecha_emision"),
        MYSQL_TABLE_OPTIONS,
    )


class Certificate(Base):
    __tablename__ = "certificados"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    atencion_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        nullable=False,
    )
    establecimiento_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "establecimientos.id",
            name="fk_certificados_establecimiento",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    profesional_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "profesionales.id",
            name="fk_certificados_profesional",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    numero_certificado: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_emision: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    consultorio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    admision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'EMITIDO'")
    )

    atencion: Mapped["Attention"] = relationship(
        back_populates="certificados",
        foreign_keys=[atencion_id, profesional_id],
        overlaps="profesional,certificados",
    )
    establecimiento: Mapped["Establishment"] = relationship(
        back_populates="certificados"
    )
    profesional: Mapped["Professional"] = relationship(
        back_populates="certificados",
        foreign_keys=[profesional_id],
        overlaps="atencion,certificados",
    )
    prestaciones: Mapped[list["CertificateService"]] = relationship(
        back_populates="certificado", order_by="CertificateService.numero_orden"
    )

    __table_args__ = (
        # The composite FK prevents a direct SQL insert from attributing a
        # certificate to somebody other than the professional of its attention.
        # Co-signature deliberately needs a separate model/use case.
        ForeignKeyConstraint(
            ["atencion_id", "profesional_id"],
            ["atenciones.id", "atenciones.profesional_id"],
            name="fk_certificados_atencion_profesional",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        CheckConstraint(
            "estado IN ('EMITIDO', 'ANULADO')",
            name="ck_certificados_estado_valido",
        ),
        UniqueConstraint(
            "establecimiento_id",
            "numero_certificado",
            name="uq_certificados_eess_numero",
        ),
        Index("idx_certificados_atencion", "atencion_id"),
        MYSQL_TABLE_OPTIONS,
    )


class CertificateService(Base):
    __tablename__ = "certificado_prestaciones"

    certificado_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "certificados.id",
            name="fk_certificado_prestaciones_certificado",
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
            name="fk_certificado_prestaciones_prestacion",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )

    certificado: Mapped["Certificate"] = relationship(back_populates="prestaciones")
    prestacion: Mapped["ServiceOffering"] = relationship(
        "ServiceOffering", back_populates="certificados_prestacion"
    )

    __table_args__ = (MYSQL_TABLE_OPTIONS,)


class DocumentSequence(Base):
    """Locked per-site/year counter used to allocate document numbers safely."""

    __tablename__ = "documento_series"

    tipo: Mapped[str] = mapped_column(String(30), primary_key=True)
    establecimiento_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "establecimientos.id",
            name="fk_documento_series_establecimiento",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    periodo: Mapped[str] = mapped_column(String(20), primary_key=True)
    siguiente_numero: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), nullable=False, server_default=text("1")
    )

    __table_args__ = (MYSQL_TABLE_OPTIONS,)
