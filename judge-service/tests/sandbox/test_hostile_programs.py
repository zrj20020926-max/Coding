import os

import pytest

from app.core.config import Settings
from app.domain.models import SubmissionStatus
from app.infrastructure.sandbox import DockerSandbox

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(
        os.getenv("RUN_SANDBOX_TESTS") != "1",
        reason="set RUN_SANDBOX_TESTS=1 to execute hostile programs in Docker",
    ),
]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(
        _env_file=None,
        sandbox_output_limit_bytes=64 * 1024,
        sandbox_disk_limit_bytes=16 * 1024 * 1024,
        sandbox_pids_limit=16,
    )


@pytest.fixture(scope="module")
def sandbox(settings: Settings) -> DockerSandbox:
    return DockerSandbox(settings)


@pytest.mark.asyncio
async def test_node_network_and_privileged_file_access_are_blocked(
    sandbox: DockerSandbox,
) -> None:
    source = b"""\
const fs = require('fs');
const net = require('net');
let blocked = 0;
try { fs.readFileSync('/etc/shadow'); } catch (_) { blocked += 1; }
(async () => { await new Promise((resolve) => {
  const socket = net.createConnection({ host: '1.1.1.1', port: 53 });
  socket.setTimeout(100);
  socket.on('connect', () => { socket.destroy(); resolve(); });
  socket.on('error', () => { blocked += 1; resolve(); });
  socket.on('timeout', () => { blocked += 1; socket.destroy(); resolve(); });
}); console.log(blocked === 2 ? 'blocked' : 'unsafe'); })();
"""
    result = await sandbox.run_case("nodejs", source, None, b"", 1000, 64)
    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout.strip() == b"blocked"


@pytest.mark.asyncio
async def test_dead_loop_is_killed_by_wall_clock_limit(sandbox: DockerSandbox) -> None:
    result = await sandbox.run_case("nodejs", b"while (true) {}", None, b"", 200, 64)
    assert result.status is SubmissionStatus.TIME_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_memory_explosion_is_classified(sandbox: DockerSandbox) -> None:
    source = b"const a=[]; while (true) a.push(Buffer.alloc(1024*1024));"
    result = await sandbox.run_case("nodejs", source, None, b"", 5000, 64)
    assert result.status is SubmissionStatus.MEMORY_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_fork_bomb_is_contained_by_pid_limit(sandbox: DockerSandbox) -> None:
    result = await sandbox.run_case(
        "nodejs",
        (
            b"const {spawn}=require('child_process'); while(true) "
            b"spawn(process.execPath,['-e','setInterval(()=>{},1000)']);"
        ),
        None,
        b"",
        2000,
        64,
    )
    assert result.status in {
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.TIME_LIMIT_EXCEEDED,
    }


@pytest.mark.asyncio
async def test_excessive_output_is_stopped(sandbox: DockerSandbox) -> None:
    source = b"while (true) console.log('x'.repeat(1024));"
    result = await sandbox.run_case("nodejs", source, None, b"", 2000, 64)
    assert result.status is SubmissionStatus.OUTPUT_LIMIT_EXCEEDED
    assert result.diagnostic == "output limit exceeded"


@pytest.mark.asyncio
async def test_javascript_syntax_error_is_compile_error(sandbox: DockerSandbox) -> None:
    rejected = await sandbox.compile("nodejs", b"const broken = ;")
    assert rejected.succeeded is False
    assert rejected.diagnostic


@pytest.mark.asyncio
async def test_v8_readline_print_and_restricted_globals(sandbox: DockerSandbox) -> None:
    source = b"""\
const [a, b] = readline().trim().split(/\\s+/).map(Number);
if ([typeof require, typeof process, typeof Buffer, typeof document].some(v => v !== 'undefined')) {
  print('unsafe');
} else {
  print(a + b);
}
"""
    compiled = await sandbox.compile("javascript-v8", source)
    assert compiled.succeeded is True
    result = await sandbox.run_case("javascript-v8", source, None, b"20 22\n", 1000, 64)
    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == b"42\n"


@pytest.mark.asyncio
async def test_v8_rejects_node_api_and_node_has_no_dom(sandbox: DockerSandbox) -> None:
    v8 = await sandbox.run_case(
        "javascript-v8", b"require('fs');", None, b"", 1000, 64
    )
    node = await sandbox.run_case("nodejs", b"document.body", None, b"", 1000, 64)
    assert v8.status is SubmissionStatus.RUNTIME_ERROR
    assert node.status is SubmissionStatus.RUNTIME_ERROR
