param(
    [string]$DatabaseRoot
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $repo '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create root .venv and install backend/requirements-profile-tests.txt first' }
if (-not $DatabaseRoot) { $DatabaseRoot = Join-Path $repo 'database' }
if (-not (Test-Path -LiteralPath $DatabaseRoot -PathType Container)) {
    throw 'Pass -DatabaseRoot <PR-2-checkout/database>; database infrastructure is a separate dependency'
}
$DatabaseRoot = (Resolve-Path -LiteralPath $DatabaseRoot).Path
foreach ($file in @('compose.test.yml','schema.sql','migrations/002_pulse_features.sql','migrations/003_integrity.sql','tests/fixtures/base.sql','tests/fingerprint.sql')) {
    if (-not (Test-Path -LiteralPath (Join-Path $DatabaseRoot $file) -PathType Leaf)) {
        throw "Missing database dependency: $file"
    }
}
$compose = Join-Path $DatabaseRoot 'compose.test.yml'
$project = 'theyabliki-profile-' + [guid]::NewGuid().ToString('N').Substring(0,12)
$previous = @{}
foreach ($key in @('DB_TEST_PASSWORD','DB_TEST_PORT','PROFILE_TEST_DATABASE_URL','NEWS_IDENTITY_TEST_DATABASE_URL','NEWS_IDENTITY_DATABASE_ROOT','PYTHON_DOTENV_DISABLED')) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key,'Process')
}
$env:DB_TEST_PASSWORD = [guid]::NewGuid().ToString('N')
if (-not $env:DB_TEST_PORT) { $env:DB_TEST_PORT = '55435' }
$env:PYTHON_DOTENV_DISABLED = '1'
function Compose {
    & docker compose -p $project -f $compose @args
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed: $($args -join ' ')" }
}
function Sql([string]$file) {
    Compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U audit_user -d theyabliki_test -f $file
}
Write-Output "Isolated profile test project: $project"
Write-Output "Database infrastructure: $DatabaseRoot"
try {
    Compose config --quiet
    Compose up -d --wait --wait-timeout 90
    Sql '/audit/schema.sql' | Out-Null
    Sql '/audit/migrations/002_pulse_features.sql' | Out-Null
    Sql '/audit/migrations/003_integrity.sql' | Out-Null
    $newsMigration = Join-Path $DatabaseRoot 'migrations/004_news_external_identity.sql'
    if (Test-Path -LiteralPath $newsMigration -PathType Leaf) {
        Sql '/audit/migrations/004_news_external_identity.sql' | Out-Null
        Sql '/audit/migrations/004_news_external_identity.sql' | Out-Null
    }
    Sql '/audit/tests/fixtures/base.sql' | Out-Null
    $before = Compose exec -T postgres psql -X -At -U audit_user -d theyabliki_test -f /audit/tests/fingerprint.sql
    $env:PROFILE_TEST_DATABASE_URL = "postgresql+asyncpg://audit_user:$($env:DB_TEST_PASSWORD)@127.0.0.1:$($env:DB_TEST_PORT)/theyabliki_test"
    if (Test-Path -LiteralPath $newsMigration -PathType Leaf) {
        $env:NEWS_IDENTITY_TEST_DATABASE_URL = $env:PROFILE_TEST_DATABASE_URL
        $env:NEWS_IDENTITY_DATABASE_ROOT = $DatabaseRoot
    } else {
        # An older separate database checkout must not trigger 004 tests elsewhere.
        Remove-Item Env:NEWS_IDENTITY_TEST_DATABASE_URL -ErrorAction SilentlyContinue
        Remove-Item Env:NEWS_IDENTITY_DATABASE_ROOT -ErrorAction SilentlyContinue
    }
    & $python -B -m pytest -c (Join-Path $repo 'backend/pytest.ini') (Join-Path $repo 'backend/tests') -q
    if ($LASTEXITCODE -ne 0) { throw 'Profile tests failed' }
    $after = Compose exec -T postgres psql -X -At -U audit_user -d theyabliki_test -f /audit/tests/fingerprint.sql
    if (($before -join "`n") -cne ($after -join "`n")) { throw 'Synthetic baseline changed' }
    Write-Output 'PASS: profile tests and synthetic baseline preserved'
} finally {
    Compose stop
    foreach ($key in $previous.Keys) { [Environment]::SetEnvironmentVariable($key,$previous[$key],'Process') }
    Write-Output "Stopped; container and volume retained: $project"
}
