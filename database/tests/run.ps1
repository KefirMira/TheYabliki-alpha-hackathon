$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot '../compose.test.yml'
# A unique Compose project isolates both container names and the named volume.
$project = 'theyabliki-db-check-' + [guid]::NewGuid().ToString('N').Substring(0,12)
$generatedPassword = -not $env:DB_TEST_PASSWORD
if ($generatedPassword) { $env:DB_TEST_PASSWORD = [guid]::NewGuid().ToString('N') }
function Compose {
    & docker compose -p $project -f $compose @args
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed: $($args -join ' ')" }
}
function SqlFile([string]$file) {
    Compose exec -T postgres psql -X -v ON_ERROR_STOP=1 -U audit_user -d theyabliki_test -f $file
}
Write-Output "Test project: $project (volume will be retained)"
try {
    Compose config --quiet
    Compose up -d --wait --wait-timeout 90
    SqlFile '/audit/schema.sql'
    # Only invented fixtures are loaded; private hackathon data is never mounted.
    SqlFile '/audit/tests/fixtures/base.sql' | Out-Null
    $before = Compose exec -T postgres psql -X -At -v ON_ERROR_STOP=1 -U audit_user -d theyabliki_test -f /audit/tests/fingerprint.sql
    SqlFile '/audit/migrations/002_pulse_features.sql'
    SqlFile '/audit/migrations/003_integrity.sql'
    SqlFile '/audit/tests/fixtures/pulse.sql'
    $pulseBefore = Compose exec -T postgres psql -X -At -v ON_ERROR_STOP=1 -U audit_user -d theyabliki_test -f /audit/tests/pulse_fingerprint.sql
    SqlFile '/audit/tests/verify.sql'
    SqlFile '/audit/migrations/002_pulse_features.sql'
    SqlFile '/audit/migrations/003_integrity.sql'
    SqlFile '/audit/tests/verify.sql'
    $after = Compose exec -T postgres psql -X -At -v ON_ERROR_STOP=1 -U audit_user -d theyabliki_test -f /audit/tests/fingerprint.sql
    $pulseAfter = Compose exec -T postgres psql -X -At -v ON_ERROR_STOP=1 -U audit_user -d theyabliki_test -f /audit/tests/pulse_fingerprint.sql
    if (($pulseBefore -join "`n") -cne ($pulseAfter -join "`n")) { throw 'Pulse fixture fingerprints changed' }
    if (($before -join "`n") -cne ($after -join "`n")) { throw 'Seed fingerprints changed' }
    Write-Output 'PASS: migration replay and complete seed row fingerprints unchanged'
    $after
    $pulseAfter
} finally {
    # Stop only this newly generated project. Never delete containers or volumes.
    Compose stop
    if ($generatedPassword) { Remove-Item Env:DB_TEST_PASSWORD }
    Write-Output "Retained project: $project"
}
