# Docker: construcción, arranque y actualización

Revisión: 20/10/2026. El stack contiene MySQL 8.4 LTS y una imagen con la SPA
Vue compilada más FastAPI, Python 3.12 y las migraciones actuales del repositorio.
Node 24 se usa solo para construir el frontend. No se necesita otro servidor web.

## Primera instalación

1. Instalar y abrir Docker Desktop con motor Linux (en Windows), o Docker Engine
   con Compose en Linux. `docker version` debe mostrar cliente **y servidor**.
2. Copiar `.env.docker.example` a `.env.docker`, sin reemplazar un archivo existente.
3. Definir contraseñas nuevas de MySQL y una `SECRET_KEY` aleatoria, por ejemplo
   generada con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Producción rechaza la clave de ejemplo. No se usan las cuentas de desarrollo
   mencionadas en el README para crear usuarios de Docker.
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

El volumen `mysql_data` pertenece al proyecto Compose `ipress`. Los datos de
MySQL local fuera de Docker **no se copian** automáticamente al contenedor.

## Qué hace el arranque

- Compose espera una consulta autenticada de MySQL con el usuario de la aplicación.
- El entrypoint aplica `alembic upgrade head`, incluyendo las migraciones nuevas.
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

Si la terminal de Windows no encuentra `docker`, agregar a PATH
`C:\Program Files\Docker\Docker\resources\bin`, o usar la ruta completa del
ejecutable. Tener instalada la CLI no significa que el motor esté arrancado.

## Referencias oficiales

- [Docker: orden de arranque y salud en Compose](https://docs.docker.com/compose/how-tos/startup-order/).
- [Docker: exclusiones del contexto de construcción](https://docs.docker.com/build/concepts/context/#dockerignore-files).
- [PyMySQL: dependencias de autenticación RSA](https://pymysql.readthedocs.io/en/latest/user/installation.html).
- [Uvicorn: proxies y cabeceras reenviadas](https://uvicorn.dev/deployment/).
- [MySQL: actualización de una instalación Docker](https://dev.mysql.com/doc/refman/8.0/en/upgrade-docker-mysql.html).
