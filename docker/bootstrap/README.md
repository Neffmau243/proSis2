# Datos privados de la instalación

`arequipa.json.gz` es la copia privada para inicializar Docker. Contiene usuarios
con hashes bcrypt, catálogos, profesionales/asignaciones y las fichas maestras de
pacientes cuyo ubigeo de residencia empieza por 04, junto con sus responsables.
Incluye solo datos activos y excluye las etiquetas de pruebas E2E, TEST, DEMO,
PRUEBA y las historias identificadas de pruebas UI/PRB. No incluye atenciones, documentos,
riesgos ligados a atenciones, auditorías ni sesiones.

El archivo no se versiona ni se copia a la imagen. Compose monta este directorio
en `/bootstrap` como solo lectura. Activar en `.env.docker`:

```dotenv
IPRESS_BOOTSTRAP_FILE=/bootstrap/arequipa.json.gz
```

Exportar desde la base configurada en `.env` a un archivo nuevo:

```powershell
python -m app.scripts.docker_bootstrap export --output docker/bootstrap/arequipa.json.gz
```

La exportación rechaza sobrescribir un archivo existente. Al trasladar el proyecto
a otra máquina, copiar también este archivo privado, además de `.env.docker`.

La migración 0042 importa la copia cuando se configura su ruta. Las claves y los
IDs se remapean por identidad; una base recién creada adopta la configuración
exportada y las claves cifradas actuales. Si la instalación ya tiene actividad,
se agregan solo los registros faltantes y se conservan los existentes.

Para cargar una copia en una base donde la revisión 0042 ya se aplicó:

```powershell
docker compose --env-file .env.docker exec -T app python -m app.scripts.docker_bootstrap restore --input /bootstrap/arequipa.json.gz
```

El administrador exportado puede iniciar sesión con su contraseña actual. No se
requiere `CREATE_ADMIN_USERNAME` ni se reinician las contraseñas al arrancar.
