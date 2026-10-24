# Entrega a DevOps: producción, pruebas y recuperación

Este paquete prepara un servidor Linux con Docker Compose por entorno. Dominio,
DNS, servidor y acceso a GitHub todavía debe proporcionarlos DevOps. No incluye
infraestructura contratada ni modifica las cuentas/contraseñas de la instalación.
La copia privada de pacientes viaja por separado de Git y de las imágenes.

## Qué se entrega

| Archivo | Función |
| --- | --- |
| `deploy/compose.yml` | MySQL y app en redes privadas; solo Caddy publica 80/443 |
| `deploy/Caddyfile` | HTTPS y renovación automática de certificados |
| `deploy/ops.py` | Generación de secretos, despliegue, backup, restauración de prueba y recuperación |
| `deploy/systemd/` | Backup diario con restauración de prueba |
| `.github/workflows/ci.yml` | Calidad, MySQL, frontend, Docker, E2E ficticio y recuperación |
| `.github/workflows/release.yml` | Publicar imagen, probar ese digest, staging y producción |
| `.github/workflows/rollback.yml` | Recuperación manual del despliegue anterior |

## 1. Preparar cada servidor una vez

Usar Linux con Python 3.12, Docker Engine y Compose v2, Git y un runner de GitHub
Actions propio. Staging y producción deben tener hosts, volúmenes, secretos y
datos separados. El runner necesita acceso al daemon Docker y a los directorios
de su entorno; no ejecutar trabajos de PR en estos runners. Restringir el grupo
de runners al repositorio y a los workflows de despliegue de la rama protegida.
Los trabajos de PR se ejecutan en runners hospedados por GitHub.

Crear DNS A (y AAAA solo si IPv6 funciona) apuntando cada dominio a su servidor.
Permitir entrada TCP 80 y 443, y SSH únicamente desde la red administrativa.
No abrir 3306 ni 8000. Aplicar las reglas en el firewall del proveedor/host,
considerando que Docker configura sus propias reglas de publicación de puertos.
Permitir salida para DNS, hora, GHCR y autoridades de certificados. Caddy necesita
que el dominio resuelva al servidor y 80/443 sean alcanzables para HTTPS público.

Clonar la revisión aprobada y preparar directorios del usuario de operaciones
(ejemplo `ipress`; adaptar ese nombre al usuario del runner):

```sh
sudo install -d -m 0700 -o ipress -g ipress /etc/ipress
sudo install -d -m 0700 -o ipress -g ipress /var/backups/ipress/production
sudo install -d -m 0700 -o ipress -g ipress /var/lib/ipress/production
```

Ejecutar como ese usuario, con los valores reales:

```sh
python3 deploy/ops.py --env /etc/ipress/production.env init \
  --project ipress_production --domain salud.example.org --email devops@example.org \
  --backup-dir /var/backups/ipress/production --state-dir /var/lib/ipress/production
```

El comando genera claves aleatorias diferentes para JWT, MySQL app y MySQL root.
No sobrescribe un entorno existente. Los secretos quedan en archivos individuales
de `/etc/ipress/production/secrets/`, fuera de Git. El directorio tiene modo 0700;
los archivos se montan de solo lectura y pueden ser leídos por el UID 10001 de la
app. Compose no incluye sus valores en las variables visibles en `docker inspect`.
Resguardar también estos archivos: son necesarios para recuperar el servicio.

Para **conservar usuarios y pacientes actuales**, copiar por un canal privado
`docker/bootstrap/arequipa-completa-20261024.json.gz` al `BOOTSTRAP_DIR` indicado
en el env y agregar:

```dotenv
IPRESS_BOOTSTRAP_FILE=/bootstrap/arequipa-completa-20261024.json.gz
```

La copia incluye el ADMIN actual. No configurar otro administrador en ese caso.
El snapshot debe poder leerse desde el contenedor: archivo 0444 dentro del
directorio privado 0700. El arranque comprueba su huella después de migrar y carga
una sola vez cada contenido, aunque la revisión 0042 ya estuviera aplicada. La
revisión 0042 mantiene también la carga histórica para la primera instalación.
La conciliación manual sigue documentada en `DOCKER.md`.

Para **staging nuevo sin pacientes reales**, repetir `init` con su propio dominio,
proyecto `ipress_staging`, rutas `/.../staging` y `--admin-username admin`. Antes,
leer la contraseña elegida sin mostrarla ni escribirla en argumentos:

```sh
read -rs -p 'Clave inicial de staging (8 dígitos): ' IPRESS_INITIAL_ADMIN_PASSWORD
export IPRESS_INITIAL_ADMIN_PASSWORD
# Ejecutar aquí init con --admin-username admin y los parámetros de staging.
unset IPRESS_INITIAL_ADMIN_PASSWORD
```

No trasladar datos de producción a staging. Las migraciones mantienen los
catálogos/cuentas heredadas existentes según la decisión del responsable del
proyecto. Los E2E agregan únicamente personas y pacientes ficticios en sus propias
bases temporales y no se ejecutan contra el servidor de producción.

## 2. Configurar GitHub una vez

La sesión local debe autenticarse antes de hacer push: `gh auth login -h github.com`.
El remoto del proyecto es `https://github.com/Neffmau243/proSis2.git`.

1. Subir los cambios por una rama/PR y exigir que pase el workflow `CI` antes de
   integrar a la rama predeterminada. Proteger esa rama y revisar cambios a
   `.github/workflows/` y `deploy/`.
2. Habilitar GitHub Actions y permitir publicación en GHCR con `GITHUB_TOKEN`.
   El paquete debe conceder al repositorio permiso de lectura/escritura según el
   job. No almacenar contraseñas de MySQL, JWT ni pacientes en GitHub.
3. Crear environments `staging` y `production`. Registrar runners Linux x64 con
   labels `ipress-staging` e `ipress-production`, respectivamente.
4. En cada environment, definir variables `APP_URL=https://dominio-real` y
   `DEPLOY_ENV_FILE=/etc/ipress/staging.env` o `/etc/ipress/production.env`.
5. Si el plan/repositorio lo permite, exigir revisión en el environment
   `production`. Si no permite esa protección, acordar el control de promoción
   antes de activar CD. No asumir que el YAML crea estas reglas administrativas.
6. Al terminar la preparación, establecer variable del **repositorio**
   `DEPLOY_ENABLED=true`. Sin ella se publica y prueba la imagen, pero no se
   despacha un despliegue a los servidores.

El pipeline Release solo consume CI exitoso de un **push al repositorio y rama
predeterminada**, nunca código ni artefactos de PR/forks. Descarta un CI de un
commit que ya fue superado en esa rama, para no desplegar una versión antigua
porque sus pruebas terminaron más tarde. Publica
`ghcr.io/<owner>/<repo>:sha-<commit completo>` y promueve el **mismo digest
`@sha256:...`**. Vuelve a ejecutar el E2E contra esa imagen publicada, después
despliega staging y comprueba HTTPS; solo si funciona avanza a producción.
Publicar una imagen no requiere que ya exista servidor.

## 3. Primer despliegue o despliegue manual

Desde la revisión aprobada y autenticado a GHCR si el paquete es privado:

```sh
python3 deploy/ops.py --env /etc/ipress/production.env deploy \
  --image ghcr.io/owner/repository@sha256:DIGEST_COMPLETO_PUBLICADO
```

Se descargan imágenes antes de interrumpir el servicio. El despliegue tiene una
**ventana de mantenimiento**: detiene Caddy y app, realiza backup/restauración de
prueba si hay base existente, ejecuta migraciones una sola vez, espera salud de
app+DB y abre HTTPS. Comprueba certificado válido, API y ruta SPA pública.
La primera carga sin base anterior no tiene versión previa para recuperar.
El Caddyfile que monta el contenedor se conserva en `STATE_DIR`, de modo que
limpiar el workspace del runner no impide reiniciar el servicio. En cada entrega
se instala la configuración revisada y se recrea el proxy para cargarla.

`STATE_DIR/release.json` guarda digest, revisión, firma del esquema y respaldo de
la versión anterior. Los locks de operaciones evitan que timer y despliegue
modifiquen el entorno a la vez. Los despliegues GitHub también están serializados.
El digest activo se toma de ese estado en las operaciones posteriores; no hace
falta editar manualmente el `APP_IMAGE` de la plantilla después de cada entrega.
Los reinicios de app no ejecutan otra vez migraciones.
Las entregas de aplicación tampoco actualizan MySQL: se conserva el contenedor
existente y se rechaza un cambio de referencia de imagen de DB. Una actualización
de MySQL se planifica por separado, con respaldo previo y su procedimiento oficial.
Los backups registran el digest de la imagen MySQL realmente usada, para que la
restauración de prueba utilice exactamente esa imagen.

## 4. Respaldo automático y copia externa

Instalar una copia estable del directorio `deploy/` en
`/opt/ipress/ops/deploy/` y mantenerla actualizada desde una revisión aprobada.
El usuario del timer debe poder leer la configuración y usar Docker (la unidad
se ejecuta como root por defecto; se puede configurar `User=ipress` con un drop-in).

```sh
sudo install -d -m 0755 /opt/ipress/ops/deploy
sudo cp deploy/ops.py deploy/compose.yml deploy/Caddyfile deploy/production.env.example /opt/ipress/ops/deploy/
sudo cp deploy/systemd/ipress-backup@.service deploy/systemd/ipress-backup@.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ipress-backup@production.timer
sudo systemctl start ipress-backup@production.service
sudo systemctl status ipress-backup@production.service
```

El timer ejecuta backup diario a las 02:30, con variación de hasta 15 minutos,
y recupera una ejecución perdida al volver a encender. Cambiar calendario con
un drop-in si DevOps necesita otro horario; ocurre en la zona horaria del host.

Cada copia contiene un dump lógico gzip de MySQL, con SHA-256, proyecto, fecha y
revisión Alembic en un manifiesto. Usa `--single-transaction` para tablas InnoDB;
no ejecutar DDL ajeno al proceso durante la copia. La verificación levanta un
MySQL nuevo **sin red ni puertos**, restaura el SQL, comprueba revisión, tablas,
conteos y `CHECK TABLE`; después elimina solo ese contenedor y su volumen anónimo.

Se conservan 14 copias verificadas por defecto (`BACKUP_KEEP`), además del respaldo
protegido de recuperación. Una copia fallida no elimina el respaldo anterior.
`STATE_DIR/last-backup.json` y `last-restore-drill.json` permiten vigilar ejecución
y antigüedad. DevOps debe conectar fallos de systemd/antigüedad a su monitorización.

**Resistencia a pérdida del servidor:** configurar `BACKUP_COPY_DIR` apuntando a
un destino externo previamente montado y cifrado (la ruta debe ser el punto de
montaje), con su propia retención y
monitorización. El script copia dump+manifiesto y comprueba SHA-256; si falta el
destino, falla. No se crea una carpeta local para simular un montaje ausente.
El destino físico/cifrado depende del almacenamiento que contrate DevOps.
Los dumps locales contienen información privada; proteger el disco y su acceso.

Ejecución/verificación manual:

```sh
python3 deploy/ops.py --env /etc/ipress/production.env backup --verify
python3 deploy/ops.py --env /etc/ipress/production.env drill --backup /ruta/copia.sql.gz
journalctl -u ipress-backup@production.service --since yesterday
```

## 5. Recuperar una versión

Si un candidato falla y el esquema no cambió, se intenta volver automáticamente
a la imagen previa y se verifica HTTPS. Se comparan revisión **y estructura**:
una migración MySQL puede dejar DDL parcial aunque Alembic no cambie de revisión.
Si cambió el esquema, se deja el servicio detenido para una recuperación explícita;
no se ejecuta `alembic downgrade` ni se descartan escrituras automáticamente.

Para volver manualmente a la imagen anterior cuando el esquema es compatible:

```sh
python3 deploy/ops.py --env /etc/ipress/production.env rollback --confirm-project ipress_production
```

Si el esquema cambió, recuperar también el dump previo requiere una decisión
explícita: **se perderán las escrituras posteriores a ese respaldo**. El comando
detiene el servicio y guarda primero otra copia de seguridad verificable:

```sh
python3 deploy/ops.py --env /etc/ipress/production.env rollback \
  --confirm-project ipress_production --restore-database
```

La acción manual `Recover previous release` ofrece el mismo procedimiento por
environment y confirmación de proyecto. Mantener disponible en GHCR el digest
anterior y las credenciales del host; la retención del registro no debe eliminarlo.

Para pérdida total del host: restaurar archivos de configuración/secretos y la
copia externa; arrancar un MySQL nuevo de la misma versión, importar el dump
validado y desplegar su digest registrado, antes de abrir acceso. El mecanismo de
rollback cubre la instalación cuyo estado persiste; no reconstruye por sí solo
un servidor perdido ni recupera archivos que nunca se copiaron fuera.

## Comprobaciones antes de habilitar CD

- CI completo verde para la revisión que se entrega.
- Staging accesible con certificado válido y prueba funcional aprobada.
- Base y app sin puertos publicados; administración del host restringida.
- Timer ejecutado, restauración verificada y copia externa recibida.
- Variables, runners y protección de environments configurados.
- Configuración privada y copia Arequipa excluidas de Git y de la imagen.

Pruebas reproducibles sin datos privados:

```sh
python tests/e2e/run_docker_staff_fua.py --synthetic --output output/docker-e2e-ci
python tests/e2e/verify_operations.py --output output/recovery-ci
```

La primera necesita Node 24, `npm ci` y `npx playwright install --with-deps chromium`
en `frontend/`. La segunda usa stdlib Python y Docker, comprueba HTTPS con CA
local de pruebas, despliegues, backup/restore, rollback y rechazo de DDL parcial.
En esta prueba solo se sustituye el transporte al registro por una imagen local;
la publicación GHCR se verifica al ejecutar Release en GitHub autenticado.
La prueba de normalización del ETL privado se omite cuando esa herramienta no
está instalada en el checkout; las pruebas de la aplicación y sus dominios siguen
siendo obligatorias. No se debe subir `etlSis/` para satisfacer una importación
de pruebas: contiene material de trabajo privado.

## Documentación oficial

- [Caddy: HTTPS automático](https://caddyserver.com/docs/automatic-https)
- [Docker Compose: secretos](https://docs.docker.com/compose/how-tos/use-secrets/)
- [GitHub: registro de contenedores](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [GitHub: environments y disponibilidad de protecciones](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [MySQL: mysqldump](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html)
