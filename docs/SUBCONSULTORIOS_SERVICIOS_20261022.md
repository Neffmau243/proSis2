# Creación de subconsultorios por servicio

La creación desde un consultorio padre ahora pide **Servicio / especialidad** en
primer plano, con todos los servicios habilitados visibles como una lista. En
Medicina aparecen MEDICINA GENERAL, DANT, PEDIATRIA, GINECOLOGIA y MEDICINA.
Se elige una opción activa de los servicios habilitados del padre;
el nuevo subconsultorio conserva su sede y área y guarda ese único servicio en
`servicios_codigos`. El nombre y código se completan desde el catálogo y pueden
ajustarse en **Nombre y código**, por ejemplo si el código ya existe en la sede.

La creación exige una selección explícita. Si el padre no tiene servicios activos,
se informa el motivo y se bloquea la creación. Si solo tiene el servicio general
de su área, se explica que todavía no tiene servicios o especialidades adicionales.

En Laboratorio, el catálogo vigente ofrece únicamente `ESPECIALIDADES:002`
(LABORATORIO). La relación `AREA_SERVICES` no contiene servicios adicionales de
esa área. Puede ampliarse mediante **Agregar servicio**; los servicios de Medicina
no se ofrecen como servicios de Laboratorio.

Desde un consultorio principal, **Agregar servicio** permite habilitar un servicio
existente del catálogo del área o registrar uno por nombre. El registro se guarda
en el catálogo y se habilita inmediatamente en ese consultorio, aunque luego se
cancele la creación del subconsultorio. La opción recién agregada queda seleccionada.
Otros consultorios de la misma área pueden habilitarla desde su catálogo.

Los nuevos servicios usan el código reservado `SRV-<16 hex>` y el grupo
`SERVICIO_AREA:<código de área>` en el catálogo existente, sin migración de esquema.
La API GET/POST `/{office_id}/servicios` requiere `CONSULTORIO_GESTIONAR`, valida
el área y el estado y restringe las altas al consultorio principal. El catálogo,
la lista habilitada y la auditoría se guardan en una transacción. Los nombres se
comparan normalizados para reutilizar entradas existentes. Estos servicios se
excluyen del catálogo de especialidades profesionales: registrarlos no concede
habilitaciones al personal.

Se reutiliza el contrato de alta existente con `consultorio_padre_id` y la lista
explícita `servicios_codigos`. No se migran ni reclasifican registros anteriores;
su edición y configuración de múltiples servicios conservan el comportamiento
existente. El backend sigue validando sede, área, servicios permitidos, códigos
duplicados y asignaciones. La herencia de asignaciones profesionales se conserva.

Verificación: 95 pruebas backend y 38 frontend aprobadas, compilación y tipos,
lint y detector visual sin hallazgos. Las pruebas backend usan HTTP y persistencia
SQLite aislada para comprobar altas, creación del subconsultorio, consumo clínico,
permisos, separación por área y rollback de auditoría. La revisión visual del
servidor local confirma los cinco servicios y el agregado en escritorio y móvil,
sin crear registros en sus datos. El diálogo mantiene la cabecera y los botones
visibles y desplaza únicamente su contenido cuando crece.

Capturas: `audits/subconsultorios-lista-servicios-20261022.png` y
`audits/subconsultorios-agregar-servicio-movil-20261022.png`.
