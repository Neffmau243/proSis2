# Revisión de Docker — 20/10/2026

## Resultado

La configuración ya construía la SPA y la API juntas con Node 24 y Python 3.12;
esas ramas siguen siendo compatibles con el proyecto. El problema no era la
ausencia del código reciente en el Dockerfile: las copias de `app/`, `migrations/`
y la compilación del frontend incluyen el estado del árbol al reconstruir.
Reiniciar un contenedor antiguo no reconstruye su imagen.

## Correcciones aplicadas

- **Reinicio con ADMIN inicial:** el entrypoint fallaba al volver a crear un usuario
  existente bajo `set -e`. Ahora usa `--if-not-exists`, conserva un ADMIN activo y
  rechaza conservar como bootstrap un usuario inactivo o sin ese rol. No cambia
  contraseñas ni promueve cuentas. La CLI normal mantiene su rechazo de duplicados.
- **Contraseña del bootstrap:** se lee con `--password-env CREATE_ADMIN_PASSWORD`,
  en lugar de poner la contraseña en los argumentos del proceso.
- **Dependencias:** separadas en `requirements-runtime.txt` y el archivo de
  desarrollo/pruebas habitual. La imagen ya no instala pytest, httpx, cobertura ni
  ruff. Agregado el extra RSA de PyMySQL para autenticación MySQL 8 y `tzdata`.
- **Salud real:** MySQL ejecuta `SELECT 1` como usuario de aplicación. La imagen
  verifica HTTP y consulta SQL; el endpoint HTTP de vida conserva su contrato.
- **Versiones y zona:** Python 3.12 con base Debian bookworm explícita, MySQL 8.4
  LTS configurable mediante `MYSQL_IMAGE`, Node 24 para build y zona America/Lima.
- **Proxy:** quitada la confianza universal `*` por defecto; se configura la lista
  de proxies confiables con `FORWARDED_ALLOW_IPS`.
- **Contexto:** excluidos `tmp`, `output`, configuraciones de herramientas, secretos
  anidados y evidencias frontend. No forman parte del contexto enviado al builder.
- **Windows/Linux:** finales LF para el entrypoint y normalización defensiva al
  construir. Un comando explícito de operación puede reemplazar el arranque web.
- **Verificación continua:** job Docker en CI y smoke test con proyecto, volumen,
  credenciales y puerto nuevos. Comprueba SPA, assets, login, migraciones, usuario
  sin privilegios, dependencias de runtime y reinicio sin duplicar el ADMIN.
- **Documentación:** guía de Docker y retiro del head Alembic/contador de tablas
  antiguos del README; se indican los comandos para consultar la versión real.

## Validación local y limitación

- `docker compose --env-file .env.docker config --quiet`: correcto, sin mostrar
  secretos ni modificar el archivo de entorno.
- YAML de CI y sintaxis de requisitos: correctos.
- `bash -n docker/entrypoint.sh`: correcto al ejecutar Git Bash fuera de la
  restricción de objetos de Windows del sandbox.
- Ruff: correcto. **30 pruebas** de bootstrap, CLI, salud y diagnóstico de Docker: aprobadas.
- **La construcción y la prueba real de contenedores no se pudieron completar.**
  Docker CLI y Compose están instalados. Se intentó iniciar Desktop; sus procesos
  abrieron, pero `docker info` agotó 30 segundos sin respuesta del motor. Los logs
  de Desktop registraron la detención de los motores locales. No se identificó
  una causa suficiente para modificar WSL, virtualización o configuración del host.
  El smoke test se detuvo en su preflight, antes de crear contenedores o volúmenes.

No se ejecutó `compose up` sobre el proyecto `ipress`, no se modificó `.env.docker`
y no se migró ni eliminó su volumen de datos. La verificación de imagen en Linux
queda pendiente hasta que Docker Desktop muestre el motor en ejecución, o hasta
la ejecución del nuevo job de CI. No se afirma que ese job ya haya pasado.

## Uso y siguientes pasos

Ver [DOCKER.md](DOCKER.md). Con el motor disponible, ejecutar primero:

```powershell
python tests/e2e/verify_docker.py --output output/docker-smoke
```

Después, al actualizar la instalación real, respaldar los datos si se cambia la
versión de MySQL y reconstruir con `docker compose --env-file .env.docker up -d --build`.
Las versiones transitivas Python siguen sin lockfile; las migraciones de varias
réplicas requieren una tarea única de despliegue. No se añadieron réplicas ni se
cambió el esquema clínico durante esta revisión.
