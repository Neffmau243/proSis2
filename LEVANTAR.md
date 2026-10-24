# Levantar IPRESS

Necesitas Docker Desktop abierto con el motor Linux. En la carpeta del proyecto:

```powershell
.\levantar.ps1
```

El comando construye el frontend y la API, espera a MySQL, aplica las migraciones,
carga la copia privada si todavía no fue importada y muestra los recuentos.
Abre [http://localhost:8000](http://localhost:8000), salvo que hayas configurado
otro puerto en `.env.docker`.

En una máquina nueva, copia primero
`docker/bootstrap/arequipa-completa-20261024.json.gz`. Contiene los 28,958
pacientes, 12 usuarios y 44 consultorios conservados. El script crea
`.env.docker` con claves nuevas si no existe; en los siguientes arranques conserva
el archivo, los datos y las contraseñas de los usuarios. No necesitas instalar
Python, Node ni MySQL en la máquina que ejecuta Docker.

Si no cambiaste el código, puedes arrancar más rápido con:

```powershell
.\levantar.ps1 -SinCompilar
```

Para detener conservando los datos:

```powershell
docker compose --env-file .env.docker stop
```

En Linux, configura `.env.docker` siguiendo [la guía Docker](docs/DOCKER.md) y usa:

```sh
docker compose --env-file .env.docker up -d --build --wait --wait-timeout 300
```

El desarrollo del backend y frontend por separado sigue documentado en
[README.md](README.md). Para un servidor con dominio y HTTPS, sigue
[docs/DEVOPS.md](docs/DEVOPS.md).

En los datos actuales hay nueve cuentas clínicas sin consultorio asignado.
El administrador debe definir sus consultorios y servicios antes de utilizarlas
para registrar atenciones. El arranque conserva esa configuración; no inventa
asignaciones clínicas.
