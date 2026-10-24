# Docker: construcción, arranque y actualización

Para el servidor con dominio/HTTPS, backups y entrega automática, seguir
[`DEVOPS.md`](DEVOPS.md). Este documento describe el stack local y sus pruebas.

Revisión: 24/10/2026. El stack contiene MySQL 8.4 LTS y una imagen con la SPA
Vue compilada más FastAPI, Python 3.12 y las migraciones actuales del repositorio.
Node 24 se usa solo para construir el frontend. No se necesita otro servidor web.

## Arranque recomendado en Windows

Con Docker Desktop abierto y la copia privada en `docker/bootstrap/`:

```powershell
.\levantar.ps1
```

Comprueba Docker y la copia antes de iniciar servicios. Si falta `.env.docker`,
lo crea desde la plantilla con claves aleatorias; conserva un archivo existente.
Construye, migra, comprueba la carga inicial y espera a que los servicios estén
saludables. `-SinCompilar` reutiliza la imagen cuando no cambió el código.
Ver [LEVANTAR.md](../LEVANTAR.md). La configuración manual sigue disponible abajo.

## Primera instalación

1. Instalar y abrir Docker Desktop con motor Linux (en Windows), o Docker Engine
   con Compose en Linux. `docker version` debe mostrar cliente **y servidor**.
2. Copiar `.env.docker.example` a `.env.docker`, sin reemplazar un archivo existente.
3. Definir contraseñas nuevas de MySQL y una `SECRET_KEY` aleatoria, por ejemplo
   generada con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Producción rechaza la clave de ejemplo. No se usan las cuentas de desarrollo
   mencionadas en el README para crear usuarios de Docker, excepto los usuarios
   que se transfieran explícitamente mediante la copia privada descrita abajo.
4. Si se desea crear el primer administrador al arrancar, definir
   `CREATE_ADMIN_USERNAME` y `CREATE_ADMIN_PASSWORD` (8 dígitos según el contrato
   actual del proyecto). Un ADMIN activo existente se conserva sin cambios.
   Un usuario existente inactivo o sin rol ADMIN provoca un error: no se promueve
   ni se reactiva automáticamente.
5. Ejecutar desde la raíz:

```powershell
docker compose --env-file .env.docker config --quiet
docker compose --env-file .env.docker up -d --build --wait --wait-timeout 240
docker compose --env-file .env.docker ps
```

Abrir `http://localhost:8000` (o el `APP_PORT` configurado). Si la instalación
local de Python ya usa el puerto 8000, elegir otro, por ejemplo `APP_PORT=8080`.
MySQL no publica su puerto al host; solo la aplicación accede a `db:3306`.

El volumen `mysql_data` pertenece al proyecto Compose `ipress`. Sin una copia
privada configurada, los datos de MySQL local **no se copian** al contenedor.

## Copia operativa de Arequipa

La revisión `20261023_0042_docker_bootstrap` carga el archivo privado indicado por
`IPRESS_BOOTSTRAP_FILE`. El arranque también comprueba esta copia después de
migrar, por lo que puede configurarse aunque 0042 ya estuviera aplicada.
Esta instalación usa `docker/bootstrap/arequipa-completa-20261024.json.gz`:

```dotenv
IPRESS_BOOTSTRAP_FILE=/bootstrap/arequipa-completa-20261024.json.gz
```

La copia completa del 24/10/2026, `arequipa-completa-20261024.json.gz`, conserva
los **28,958 pacientes de Arequipa y 12 usuarios** de la base local limpia,
además de 44 consultorios, 73 profesionales y 373 asignaciones. Se exportó con
`--selection all-master-data`: conserva también cuentas inactivas y registros
identificados como pruebas, manteniendo sus estados y contraseñas cifradas.
Para esta instalación, configurar
`IPRESS_BOOTSTRAP_FILE=/bootstrap/arequipa-completa-20261024.json.gz`.
No se copian atenciones, documentos ni auditorías de la base original. La copia
filtrada anterior del 23/10 sigue disponible como respaldo histórico;
`arequipa.json.gz` no es la copia completa actual.

Compose monta el directorio en `/bootstrap` como solo lectura. El archivo está
excluido de Git y del contexto de construcción, por lo que hay que copiarlo por
separado al trasladar la instalación a otra máquina. El administrador conserva
su contraseña actual: no se requiere `CREATE_ADMIN_USERNAME` para esta carga.

En una base recién inicializada se sincronizan los catálogos y las claves
cifradas de los usuarios que ya sembraba la revisión 0025. En una instalación
con actividad se insertan solo los registros faltantes. Los IDs se remapean por
identidad, se conserva la jerarquía de consultorios y el ámbito de sus servicios,
y se registra una auditoría de importación con los conteos y el hash del archivo.

Para exportar una copia nueva desde la base de `.env`, utilizar un archivo que
todavía no exista; nunca se sobrescribe la copia anterior automáticamente:

```powershell
python -m app.scripts.docker_bootstrap export --output docker/bootstrap/arequipa-actualizada.json.gz
```

Para trasladar todos los usuarios, consultorios y pacientes de Arequipa
conservados en la base origen, sin aplicar el filtro de activos/pruebas:

```powershell
python -m app.scripts.docker_bootstrap export --selection all-master-data --output docker/bootstrap/arequipa-completa-20261024.json.gz
```

Si la revisión 0042 ya fue aplicada antes de configurar la copia, importar con:

```powershell
docker compose --env-file .env.docker up -d --build --wait --wait-timeout 300
```

El arranque guarda la huella de una carga exitosa y omite esa misma copia en
los siguientes reinicios. Así conserva contraseñas cambiadas y bajas posteriores.
Un archivo distinto se concilia sin reemplazar contraseñas existentes. La carga
se confirma en una transacción. `docker_bootstrap restore --input ...` sigue
disponible para una conciliación manual explícita.
No elimina datos al revertir la revisión. Más detalles en
[`docker/bootstrap/README.md`](../docker/bootstrap/README.md).

**Asignaciones de las cuentas del SIS:** los nueve usuarios del SIS exportados
tienen rol PROFESIONAL, pero sus perfiles todavía no tienen área ni consultorio.
Los 62 profesionales del catálogo de origen sí tienen áreas y asignaciones.
La copia completa conserva también `medico.demo`, vinculada a ese grupo; la
copia filtrada del 23/10 excluía esa cuenta. Para registrar atenciones con las
cuentas del SIS, el administrador debe configurar las identidades y asignaciones
verificadas; el origen `Operarios` no contiene esa correspondencia.

### Recrear la instalación con una base nueva

Una imagen nueva no reemplaza los datos de un volumen existente. Para crear
la base desde cero y cargar la copia privada, después de verificar el respaldo
configurar en `.env.docker` un `MYSQL_VOLUME_NAME` nuevo y el
`IPRESS_BOOTSTRAP_FILE` correspondiente; luego ejecutar:

```powershell
docker compose --env-file .env.docker up -d --build --force-recreate --wait --wait-timeout 300
```

El volumen anterior permanece disponible para recuperación. No se requiere
restablecer Docker Desktop ni borrar volúmenes de otros proyectos. La imagen
no incluye el archivo privado: copiar también `docker/bootstrap/` al servidor.
No reutilizar un volumen MySQL con otro motor o una versión incompatible.

### Despliegue con MariaDB

El Compose principal utiliza MySQL 8.4. La migración 0039 también se verifica
en MariaDB 11.4: retira temporalmente las claves foráneas que usan
`atenciones.profesional_id` y `consultorio_id`, cambia su nulabilidad y las
restaura. MariaDB también rechaza CASCADE desde la columna padre nullable hacia
el firmante obligatorio del certificado: esa clave usa ON UPDATE RESTRICT en
MariaDB, impidiendo cambiar la asignación de una atención con certificado. En
MySQL conserva ON UPDATE CASCADE. Esto evita el error 1833 sin desactivar la
integridad referencial. Si el despliegue falló en 0039, actualizar la imagen y
volver a ejecutar `alembic upgrade head`; no marcar la migración como aplicada
mediante `stamp` ni borrar la base para ocultar el fallo.

El importador también tipa explícitamente las listas de servicios y el JSON de
auditoría, porque MariaDB refleja su alias JSON como LONGTEXT. La prueba
`tests/e2e/verify_referral_assignment_migration.py` verifica el fallo original,
upgrade/downgrade con documentos existentes, integridad de firmantes, reintento
de DDL interrumpido y carga/reimportación de la copia completa. Requiere una
base vacía desechable en `TEST_DATABASE_URL` cuyo nombre contenga `test`.

## Qué hace el arranque

- Compose espera una consulta autenticada de MySQL con el usuario de la aplicación.
- El entrypoint aplica `alembic upgrade head`, incluyendo las migraciones nuevas.
- Después comprueba la copia configurada, con independencia de que 0042 ya
  estuviera aplicada. Cada contenido se carga una sola vez; reiniciar no repone
  registros eliminados ni cambia contraseñas.
- Crea el ADMIN opcional o conserva el ya existente; la contraseña no viaja en
  los argumentos del proceso y no se modifica al reiniciar.
- Ejecuta Uvicorn como usuario `ipress`, UID 10001. El frontend sale del mismo origen.
- La comprobación de salud del contenedor verifica HTTP y `SELECT 1` en MySQL.
  `/api/v1/health` sigue siendo una comprobación de vida del proceso solamente.
- La zona horaria es `America/Lima`. `FORWARDED_ALLOW_IPS` solo debe contener
  direcciones de proxies de confianza; el valor predeterminado es `127.0.0.1`.

`WEB_CONCURRENCY` aumenta procesos dentro de un contenedor; no evita migraciones
simultáneas entre réplicas. Para varias réplicas, ejecutar migraciones una sola vez
como tarea de despliegue y arrancar las réplicas con `RUN_MIGRATIONS=false`.
Las conexiones potenciales por contenedor son `workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW)`.

## Actualizar el código desplegado

Los archivos de la máquina no se montan como código vivo dentro del contenedor.
Para incluir cambios del FUA, la gestante o cualquier otra pantalla, reconstruir:

```powershell
docker compose --env-file .env.docker up -d --build --wait --wait-timeout 240
```

El build ejecuta `npm ci` con el lockfile y compila el frontend actual; no copia
el `frontend/dist` anterior del host. `app/` y `migrations/` se copian del código
actual. Los datos siguen en el volumen. `restart` por sí solo no incorpora cambios
de código ni dependencias.

Para consultar estado o detener sin borrar los datos:

```powershell
docker compose --env-file .env.docker logs --tail 100 app
docker compose --env-file .env.docker stop
docker compose --env-file .env.docker down
```

No usar `down --volumes` sobre la instalación con datos que se desean conservar.
Antes de cambiar la versión de MySQL, hacer un respaldo y revisar el camino de
actualización de la versión instalada. El valor `MYSQL_IMAGE=mysql:8.4` fija la
rama LTS; puede mantenerse temporalmente la versión anterior explícita durante
la preparación de una actualización de un volumen existente. No bajar de versión
un directorio de datos ya actualizado.

## Dependencias y contexto

`requirements-runtime.txt` contiene las dependencias que instala la imagen.
`requirements.txt` incluye ese archivo y las herramientas de desarrollo/pruebas,
por lo que `pip install -r requirements.txt` sigue funcionando en desarrollo y CI.
`PyMySQL[rsa]` cubre la autenticación de MySQL 8 y `tzdata` asegura la zona Lima.
Los rangos Python siguen permitiendo actualizaciones compatibles: todavía no hay
un lockfile Python completo con versiones transitivas y hashes.

`.dockerignore` excluye secretos, dependencias y compilaciones locales, volcados
Access, pruebas/evidencias, `tmp`, `output` y configuración de herramientas. El
entrypoint conserva finales de línea LF incluso al trabajar desde Windows.

## Prueba aislada y CI

```powershell
python tests/e2e/verify_docker.py --output output/docker-smoke
```

La prueba usa solo la biblioteca estándar de Python y Docker. Genera credenciales
ficticias en memoria, otro puerto y un proyecto `ipress_docker_test_<identificador>`
con volumen nuevo. No lee `.env.docker` ni utiliza el volumen `ipress_mysql_data`.
Comprueba construcción, migraciones, salud de MySQL, rutas SPA/assets, login,
usuario Linux sin privilegios, ausencia de pytest/ruff y reinicio conservando un
único administrador. Después elimina exclusivamente su proyecto y volumen de
prueba. Conserva un log y un JSON sin contraseñas en el directorio de evidencia.
El job `docker` de GitHub Actions ejecuta la misma prueba.

### E2E de administrador, médico y FUA

Con Docker arrancado y la copia privada exportada, se puede probar la SPA real
servida por el contenedor, con MySQL 8.4 y un proyecto/volumen nuevos:

```powershell
python tests/e2e/run_docker_staff_fua.py --output output/docker-staff-fua --keep-running
```

El recorrido entra como administrador, completa nombre/documento/profesión/
colegiatura/área de un médico ficticio, crea su cuenta y la asigna solo a Medicina
General del C.S. Alto Selva Alegre. Luego inicia sesión como ese médico en otro
contexto de navegador, crea un paciente ficticio mediante el API del contenedor,
guarda la atención desde la SPA, emite el FUA y descarga el PDF. Comprueba los
datos del profesional, la pertenencia de la atención y la restricción del rol.

Requiere las dependencias de `frontend/` y un navegador para Playwright. En
Windows usa Edge instalado; `PLAYWRIGHT_CHROMIUM_EXECUTABLE` permite indicar otro
ejecutable. La contraseña del administrador se puede proporcionar por
`DOCKER_E2E_ADMIN_PASSWORD`; de forma predeterminada usa la cuenta local ya
transferida a la copia privada. No configura ni cambia credenciales existentes.

`stack.json` contiene el proyecto/puerto y `browser/resultado.json` los IDs y las
credenciales ficticias del médico de pruebas. Las capturas y el PDF se guardan
en `browser/`. Este directorio de evidencias es privado y no se versiona.

Sin `--keep-running`, el script elimina solo su proyecto y volumen generados al
terminar. Para repetir el navegador sobre la misma instalación de prueba:

```powershell
python tests/e2e/run_docker_staff_fua.py --output output/docker-staff-fua --reuse --keep-running
```

Cada repetición crea identidades ficticias nuevas. La base MySQL local y el
proyecto Compose habitual `ipress` no se modifican.

Si la terminal de Windows no encuentra `docker`, agregar a PATH
`C:\Program Files\Docker\Docker\resources\bin`, o usar la ruta completa del
ejecutable. Tener instalada la CLI no significa que el motor esté arrancado.

## Referencias oficiales

- [Docker: orden de arranque y salud en Compose](https://docs.docker.com/compose/how-tos/startup-order/).
- [Docker: exclusiones del contexto de construcción](https://docs.docker.com/build/concepts/context/#dockerignore-files).
- [PyMySQL: dependencias de autenticación RSA](https://pymysql.readthedocs.io/en/latest/user/installation.html).
- [Uvicorn: proxies y cabeceras reenviadas](https://uvicorn.dev/deployment/).
- [MySQL: actualización de una instalación Docker](https://dev.mysql.com/doc/refman/8.0/en/upgrade-docker-mysql.html).
