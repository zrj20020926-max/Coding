param(
    [string]$Project = "codearena-full-stack-e2e",
    [int]$FrontendPort = 18080
)

$ErrorActionPreference = "Stop"
if (-not $Project.StartsWith("codearena-full-stack-e2e")) {
    throw "Refusing to use a non-E2E Compose project"
}

$env:FULL_STACK_COMPOSE_PROJECT = $Project
$env:FULL_STACK_FRONTEND_PORT = [string]$FrontendPort
$compose = @("compose", "-p", $Project, "-f", "docker-compose.content-test.yml")
$testExit = 1

try {
    & docker @compose down -v --remove-orphans
    & docker pull node:22-bookworm-slim
    & docker pull node:22-alpine
    & docker @compose up --build -d --wait frontend-full-stack-e2e judge-service-content-test
    if ($LASTEXITCODE -ne 0) { throw "Full-stack Compose startup failed" }
    # The stack is already healthy. Do not re-run migration/bootstrap dependencies
    # while API and Judge are serving the same isolated database.
    & docker @compose run --rm --no-deps content-invariants-e2e
    if ($LASTEXITCODE -ne 0) { throw "Content invariant verification failed" }
    Push-Location frontend
    try {
        npm run test:e2e:full
        $testExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    python scripts/collect_full_stack_e2e_artifacts.py
    $sandboxIds = & docker ps -aq `
        --filter "label=codearena.role=untrusted-sandbox" `
        --filter "label=codearena.environment=codearena-full-stack-e2e"
    foreach ($sandboxId in $sandboxIds) {
        if ($sandboxId) { & docker rm -f $sandboxId | Out-Null }
    }
    & docker @compose down -v --remove-orphans
}

exit $testExit
