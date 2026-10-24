# Revisión del arranque y regresiones — 24/10/2026

El inicio recomendado en Windows es `./levantar.ps1`; las instrucciones cortas
están en [LEVANTAR.md](../LEVANTAR.md). Se probó el comando contra la instalación
Docker real. Los datos conservados son 28,958 pacientes, 12 usuarios y 44
consultorios. La actividad clínica sigue vacía.

## Cambios

- Un comando comprueba Docker y la copia privada, construye la aplicación y
  espera a que los servicios estén saludables. Muestra solamente recuentos.
- En una máquina nueva genera claves aleatorias independientes para JWT y los
  dos usuarios de MySQL. Conserva un `.env.docker` existente. Esta rama se
  verificó en una carpeta aislada con las llamadas Docker simuladas.
- La copia se comprueba después de aplicar las migraciones, incluso si 0042
  ya estaba aplicada. Se registra su carga exitosa por huella de contenido.
  Los reinicios omiten una copia ya cargada y conservan cambios posteriores.
- La carga sigue siendo transaccional. El esquema sigue siendo responsabilidad
  de Alembic; no se añadió `create_all` al inicio de la API.
- La arquitectura de controladores, servicios, repositorios, contratos y dominio
  se mantiene. Los cambios de este ajuste están en instalación y operación.

## Verificación

- 892 pruebas unitarias del backend aprobadas, incluidas 23 del importador.
- Ruff aprobado en los archivos Python modificados y sintaxis PowerShell válida.
- `alembic check` en la instalación Docker: sin operaciones nuevas pendientes.
- MariaDB 11.4.13 y MySQL 8.4.13: migraciones, conservación de historia y claves,
  downgrade protegido, reintento de DDL interrumpido, carga tardía de la copia,
  contraseñas y repetición del arranque verificados en bases temporales.
- Docker aislado: construcción, salud, rutas/assets de la SPA, login y reinicio
  sin duplicar el administrador aprobados. Se retiraron sus recursos de prueba.
- Comparación de todos los campos maestros de Docker contra la copia original,
  remapeando claves y relaciones: aprobada.

Los resultados agregados están en
`output/data-cleanup-20261024/startup-review.json`; las evidencias locales están
excluidas de Git. La comprobación no constituye una auditoría completa de todas
las pantallas ni una medición de capacidad en producción.

## Configuración clínica pendiente

Nueve cuentas activas de rol PROFESIONAL no tienen asignaciones de consultorio.
Esta situación ya existía en los datos conservados y limita el registro de
atenciones. El administrador debe establecer el consultorio y servicio de cada
cuenta a partir de sus funciones reales. No se asignaron valores por suposición.
