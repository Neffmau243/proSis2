"""ORM models for the IPRESS territorial and care-office structure."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, JSON, Boolean, Date, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import MYSQL_TABLE_OPTIONS, Base

if TYPE_CHECKING:
    from .catalog import Specialty
    from .clinical import Attention
    from .documents import Certificate, Referral
    from .patient import Patient
    from .security import Professional
    from .surveillance import NutritionalEvaluation, SurveillanceSien


class Disa(Base):
    __tablename__ = "disa"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    redes: Mapped[list[Network]] = relationship(back_populates="disa")

    __table_args__ = (
        UniqueConstraint("codigo", name="uq_disa_codigo"),
        MYSQL_TABLE_OPTIONS,
    )


class Network(Base):
    __tablename__ = "redes"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    id_disa: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "disa.id",
            name="fk_redes_disa",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    disa: Mapped[Disa] = relationship(back_populates="redes")
    microredes: Mapped[list[MicroNetwork]] = relationship(back_populates="red")

    __table_args__ = (
        UniqueConstraint("id_disa", "codigo", name="uq_redes_disa_codigo"),
        MYSQL_TABLE_OPTIONS,
    )


class MicroNetwork(Base):
    __tablename__ = "microredes"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    id_red: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "redes.id",
            name="fk_microredes_red",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    red: Mapped[Network] = relationship(back_populates="microredes")
    establecimientos: Mapped[list[Establishment]] = relationship(back_populates="microred")

    __table_args__ = (
        UniqueConstraint("id_red", "codigo", name="uq_microredes_red_codigo"),
        MYSQL_TABLE_OPTIONS,
    )


class Ubigeo(Base):
    __tablename__ = "ubigeos"

    codigo: Mapped[str] = mapped_column(CHAR(6), primary_key=True)
    departamento: Mapped[str] = mapped_column(String(100), nullable=False)
    provincia: Mapped[str] = mapped_column(String(100), nullable=False)
    distrito: Mapped[str] = mapped_column(String(100), nullable=False)
    localidad: Mapped[str | None] = mapped_column(String(150), nullable=True)
    altitud_msnm: Mapped[Decimal | None] = mapped_column(mysql.DECIMAL(8, 2), nullable=True)
    quintil: Mapped[str | None] = mapped_column(String(50), nullable=True)

    establecimientos: Mapped[list[Establishment]] = relationship(back_populates="ubigeo")
    localidades: Mapped[list[Localidad]] = relationship(back_populates="ubigeo")
    pacientes: Mapped[list[Patient]] = relationship(back_populates="ubigeo_residencia")

    __table_args__ = (
        Index("idx_ubigeos_distrito", "distrito"),
        MYSQL_TABLE_OPTIONS,
    )


class Localidad(Base):
    """A district sector with its SIS locality code (source ``Z_*`` catalogs).

    The district stays identified by its six-digit UBIGEO; the SIS code is only
    unique within that district, so the pair is the natural key.
    """

    __tablename__ = "localidades"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    ubigeo_codigo: Mapped[str] = mapped_column(
        CHAR(6),
        ForeignKey(
            "ubigeos.codigo",
            name="fk_localidades_ubigeo",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    codigo_sis: Mapped[str] = mapped_column(String(10), nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    nombre_norm: Mapped[str] = mapped_column(String(150), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    ubigeo: Mapped[Ubigeo] = relationship(back_populates="localidades")
    pacientes: Mapped[list[Patient]] = relationship(back_populates="localidad_catalogo")

    __table_args__ = (
        UniqueConstraint("ubigeo_codigo", "codigo_sis", name="uq_localidades_ubigeo_codigo"),
        UniqueConstraint("ubigeo_codigo", "nombre_norm", name="uq_localidades_ubigeo_nombre"),
        Index("ix_localidades_nombre_norm", "nombre_norm"),
        MYSQL_TABLE_OPTIONS,
    )


class Establishment(Base):
    __tablename__ = "establecimientos"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    codigo_legacy: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), nullable=True)
    id_microred: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "microredes.id",
            name="fk_establecimientos_microred",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    codigo_renaes: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: Código DIRESA/DISA de tres caracteres que entrega la sede en SIS.
    disa_codigo: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # Site defaults, independent of the account's role or medical profession.
    fua_personal_atiende: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'IPRESS'")
    )
    fua_lugar_atencion: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'INTRAMURAL'")
    )
    fua_codigo_aisped: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fua_renipress_preimpreso: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE")
    )
    codigo_ideess: Mapped[str | None] = mapped_column(String(30), nullable=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    abreviatura: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ubigeo_codigo: Mapped[str | None] = mapped_column(
        CHAR(6),
        ForeignKey(
            "ubigeos.codigo",
            name="fk_establecimientos_ubigeo",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    area_urbana: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    microred: Mapped[MicroNetwork | None] = relationship(back_populates="establecimientos")
    ubigeo: Mapped[Ubigeo | None] = relationship(back_populates="establecimientos")
    pacientes_registrados: Mapped[list[Patient]] = relationship(
        back_populates="establecimiento_registro"
    )
    consultorios: Mapped[list[Office]] = relationship(back_populates="establecimiento")
    atenciones: Mapped[list[Attention]] = relationship(back_populates="establecimiento")
    referencias_origen: Mapped[list[Referral]] = relationship(
        "Referral",
        foreign_keys="Referral.establecimiento_origen_id",
        back_populates="establecimiento_origen",
    )
    referencias_destino: Mapped[list[Referral]] = relationship(
        "Referral",
        foreign_keys="Referral.establecimiento_destino_id",
        back_populates="establecimiento_destino",
    )
    certificados: Mapped[list[Certificate]] = relationship(back_populates="establecimiento")
    vigilancia_sien: Mapped[list[SurveillanceSien]] = relationship(back_populates="establecimiento")
    evaluaciones_nutricionales: Mapped[list[NutritionalEvaluation]] = relationship(
        back_populates="establecimiento"
    )

    __table_args__ = (
        UniqueConstraint("codigo_legacy", name="uq_establecimientos_legacy"),
        UniqueConstraint("codigo_renaes", name="uq_establecimientos_renaes"),
        UniqueConstraint("codigo_ideess", name="uq_establecimientos_ideess"),
        Index("idx_establecimientos_nombre", "nombre"),
        MYSQL_TABLE_OPTIONS,
    )


class Office(Base):
    __tablename__ = "consultorios"

    id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    establecimiento_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "establecimientos.id",
            name="fk_consultorios_establecimiento",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    consultorio_padre_id: Mapped[int | None] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "consultorios.id",
            name="fk_consultorios_padre",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    area_codigo: Mapped[str | None] = mapped_column(
        String(20), ForeignKey("especialidades.codigo", name="fk_consultorios_area"), nullable=True
    )
    # NULL inherits the parent/default area services; [] intentionally disables care.
    servicios_codigos: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    especialidad_codigo: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey(
            "especialidades.codigo",
            name="fk_consultorios_especialidad",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))

    establecimiento: Mapped[Establishment] = relationship(back_populates="consultorios")
    padre: Mapped[Office | None] = relationship(
        "Office",
        back_populates="hijos",
        foreign_keys=[consultorio_padre_id],
        remote_side="Office.id",
    )
    hijos: Mapped[list[Office]] = relationship(back_populates="padre")
    especialidad: Mapped[Specialty | None] = relationship(
        "Specialty", back_populates="consultorios", foreign_keys=[especialidad_codigo]
    )
    profesionales_asignados: Mapped[list[OfficeProfessional]] = relationship(
        back_populates="consultorio"
    )
    atenciones: Mapped[list[Attention]] = relationship(back_populates="consultorio")

    __table_args__ = (
        UniqueConstraint(
            "establecimiento_id",
            "codigo",
            name="uq_consultorios_establecimiento_codigo",
        ),
        Index("idx_consultorios_padre", "consultorio_padre_id"),
        MYSQL_TABLE_OPTIONS,
    )


class OfficeProfessional(Base):
    __tablename__ = "consultorio_profesionales"

    consultorio_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "consultorios.id",
            name="fk_consultorio_profesionales_consultorio",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    profesional_id: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        ForeignKey(
            "profesionales.id",
            name="fk_consultorio_profesionales_profesional",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    fecha_inicio: Mapped[date] = mapped_column(Date, primary_key=True)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    es_responsable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("FALSE")
    )

    consultorio: Mapped[Office] = relationship(back_populates="profesionales_asignados")
    profesional: Mapped[Professional] = relationship(
        "Professional", back_populates="asignaciones_consultorio"
    )

    __table_args__ = (
        Index(
            "idx_consultorio_profesionales_vigencia",
            "consultorio_id",
            "fecha_inicio",
            "fecha_fin",
        ),
        MYSQL_TABLE_OPTIONS,
    )
