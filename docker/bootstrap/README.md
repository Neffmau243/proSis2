# Datos privados de la instalación

La copia actual es **`arequipa-completa-20261024.json.gz`**. El arranque sencillo
del proyecto está en [LEVANTAR.md](../../LEVANTAR.md).

`arequipa.json.gz` es una copia histórica filtrada. Contiene usuarios
con hashes bcrypt, catálogos, profesionales/asignaciones y las fichas maestras de
pacientes cuyo ubigeo de residencia empieza por 04, junto con sus responsables.
Incluye solo datos activos y excluye las etiquetas de pruebas E2E, TEST, DEMO,
PRUEBA y las historias identificadas de pruebas UI/PRB. No incluye atenciones, documentos,
riesgos ligados a atenciones, auditorías ni sesiones.

`arequipa-completa-20261024.json.gz` es una exportación completa de la base local
limpia: 28,958 pacientes de Arequipa, 12 usuarios y 44 consultorios. Usa la
selección explícita `all-master-data`, por lo que conserva también cuentas
inactivas y registros de pruebas. Los estados, contraseñas cifradas y
asignaciones se trasladan; no se activa ni se cambia la clave de una cuenta.
Configurar `IPRESS_BOOTSTRAP_FILE` con este nombre para desplegar esa copia.

El archivo no se versiona ni se copia a la imagen. Compose monta este directorio
en `/bootstrap` como solo lectura. Activar en `.env.docker`:

```dotenv
IPRESS_BOOTSTRAP_FILE=/bootstrap/arequipa-completa-20261024.json.gz
```

Exportar desde la base configurada en `.env` a un archivo nuevo:

```powershell
python -m app.scripts.docker_bootstrap export --output docker/bootstrap/arequipa.json.gz
```

Para conservar todos los datos maestros de Arequipa, usar
`--selection all-master-data` y un nombre de archivo nuevo. Sin esa opción se
mantiene la selección predeterminada de registros activos sin etiquetas de prueba.

La exportación rechaza sobrescribir un archivo existente. Al trasladar el proyecto
a otra máquina, copiar también este archivo privado, además de `.env.docker`.

La migración 0042 mantiene su carga histórica. Además, el entrypoint comprueba
la copia configurada después de migrar, incluso si 0042 ya estaba aplicada.
Registra la huella de una carga exitosa y omite ese mismo archivo en reinicios;
no repone bajas ni deshace cambios de contraseña posteriores. Las claves y los
IDs se remapean por identidad; una base recién creada adopta la configuración
exportada y las claves cifradas actuales. Si la instalación ya tiene actividad,
se agregan solo los registros faltantes y se conservan los existentes.

Para arrancar o actualizar con la copia configurada:

```powershell
docker compose --env-file .env.docker up -d --build --wait --wait-timeout 300
```

El administrador exportado puede iniciar sesión con su contraseña actual. No se
requiere `CREATE_ADMIN_USERNAME` ni se reinician las contraseñas al arrancar.
