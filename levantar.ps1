#Requires -Version 5.1
[CmdletBinding()]
param([switch]$SinCompilar)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$environmentFile = Join-Path $projectRoot '.env.docker'

function Read-Setting([string]$Content, [string]$Name) {
    $matchesFound = [regex]::Matches($Content, '(?m)^\s*' + [regex]::Escape($Name) + '\s*=\s*(.*?)\s*$')
    if ($matchesFound.Count -eq 0) { return '' }
    return $matchesFound[$matchesFound.Count - 1].Groups[1].Value.Trim().Trim("'").Trim('"')
}

function New-Secret {
    $bytes = New-Object byte[] 36
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) {
    $dockerPath = $dockerCommand.Source
} else {
    $dockerPath = Join-Path $env:ProgramFiles 'Docker/Docker/resources/bin/docker.exe'
}
if (-not (Test-Path -LiteralPath $dockerPath -PathType Leaf)) {
    throw 'Instala Docker Desktop y abrelo antes de levantar IPRESS.'
}

Push-Location $projectRoot
try {
    & $dockerPath info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker no responde. Abre Docker Desktop, espera que termine de iniciar y vuelve a ejecutar este comando.'
    }
    $createEnvironment = -not (Test-Path -LiteralPath $environmentFile -PathType Leaf)
    $sourceEnvironment = if ($createEnvironment) {
        Join-Path $projectRoot '.env.docker.example'
    } else { $environmentFile }
    $environmentContent = [IO.File]::ReadAllText($sourceEnvironment)
    $snapshotSetting = Read-Setting $environmentContent 'IPRESS_BOOTSTRAP_FILE'
    if (-not $snapshotSetting.StartsWith('/bootstrap/')) {
        throw 'Configura IPRESS_BOOTSTRAP_FILE=/bootstrap/arequipa-completa-20261024.json.gz en .env.docker.'
    }
    $bootstrapRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'docker/bootstrap'))
    $snapshotPath = [IO.Path]::GetFullPath((Join-Path $bootstrapRoot $snapshotSetting.Substring(11)))
    if (-not $snapshotPath.StartsWith($bootstrapRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'La copia configurada debe estar dentro de docker/bootstrap/.'
    }
    if (-not (Test-Path -LiteralPath $snapshotPath -PathType Leaf)) {
        throw ('Falta la copia privada de pacientes y usuarios. Copia el archivo en: ' + $snapshotPath)
    }
    $snapshotStream = [IO.File]::OpenRead($snapshotPath)
    try {
        if ($snapshotStream.ReadByte() -ne 31 -or $snapshotStream.ReadByte() -ne 139) {
            throw 'La copia privada no es un archivo gzip valido. Vuelve a copiarla.'
        }
    } finally { $snapshotStream.Dispose() }

    if ($createEnvironment) {
        foreach ($settingName in @('SECRET_KEY', 'MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD')) {
            $environmentContent = [regex]::Replace($environmentContent,
                '(?m)^' + $settingName + '=.*$', $settingName + '=' + (New-Secret))
        }
        $utf8 = New-Object Text.UTF8Encoding $false
        [IO.File]::WriteAllText($environmentFile, $environmentContent, $utf8)
        Write-Host 'Se creo .env.docker con claves nuevas. Conserva ese archivo para los siguientes arranques.'
    }

    $composeArguments = @('compose', '--env-file', $environmentFile, '-f',
        (Join-Path $projectRoot 'docker-compose.yml'))
    & $dockerPath @composeArguments config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Revisa los valores de .env.docker.' }
    $upArguments = @('up', '-d', '--wait', '--wait-timeout', '300')
    if (-not $SinCompilar) { $upArguments += '--build' }
    & $dockerPath @composeArguments @upArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'IPRESS no termino de iniciar. Consulta: docker compose --env-file .env.docker logs --tail 80 app db'
    }

    # Report only aggregate counts; never print passwords or patient records.
    $statusCode = @'
import json
from sqlalchemy import create_engine, text
from app.core.config import get_settings
engine = create_engine(get_settings().sqlalchemy_database_url)
try:
    with engine.connect() as connection:
        result = {name: connection.scalar(text("SELECT COUNT(*) FROM " + name))
                  for name in ("pacientes", "usuarios", "consultorios", "atenciones")}
        print(json.dumps(result))
finally:
    engine.dispose()
'@
    & $dockerPath @composeArguments exec -T app python -c $statusCode
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo comprobar la conexion con la base de datos.' }
    $port = Read-Setting $environmentContent 'APP_PORT'
    if (-not $port) { $port = '8000' }
    Write-Host ('IPRESS listo: http://localhost:' + $port)
    Write-Host 'Para detenerlo conservando los datos: docker compose --env-file .env.docker stop'
} finally {
    Pop-Location
}
