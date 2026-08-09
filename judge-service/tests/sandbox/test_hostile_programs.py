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
async def test_python_network_and_privileged_file_access_are_blocked(
    sandbox: DockerSandbox,
) -> None:
    source = b"""\
import socket
blocked = 0
try:
    open('/etc/shadow').read()
except Exception:
    blocked += 1
try:
    socket.create_connection(('1.1.1.1', 53), timeout=0.1)
except Exception:
    blocked += 1
print('blocked' if blocked == 2 else 'unsafe')
"""
    result = await sandbox.run_case("python", source, None, b"", 1000, 64)
    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout.strip() == b"blocked"


@pytest.mark.asyncio
async def test_dead_loop_is_killed_by_wall_clock_limit(sandbox: DockerSandbox) -> None:
    result = await sandbox.run_case("python", b"while True: pass", None, b"", 200, 64)
    assert result.status is SubmissionStatus.TIME_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_memory_explosion_is_classified(sandbox: DockerSandbox) -> None:
    source = b"a=[]\nwhile True: a.append(bytearray(1024*1024))"
    result = await sandbox.run_case("python", source, None, b"", 3000, 32)
    assert result.status is SubmissionStatus.MEMORY_LIMIT_EXCEEDED


@pytest.mark.asyncio
async def test_fork_bomb_is_contained_by_pid_limit(sandbox: DockerSandbox) -> None:
    result = await sandbox.run_case(
        "python", b"import os\nwhile True: os.fork()", None, b"", 2000, 64
    )
    assert result.status in {
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.TIME_LIMIT_EXCEEDED,
    }


@pytest.mark.asyncio
async def test_excessive_output_is_stopped(sandbox: DockerSandbox) -> None:
    source = b"while True: print('x' * 1024)"
    result = await sandbox.run_case("python", source, None, b"", 2000, 64)
    assert result.status is SubmissionStatus.RUNTIME_ERROR
    assert result.diagnostic == "output limit exceeded"


@pytest.mark.asyncio
async def test_cpp20_compile_run_and_compile_error(sandbox: DockerSandbox) -> None:
    accepted = await sandbox.compile(
        "cpp",
        b"#include <iostream>\nint main(){int x;std::cin>>x;std::cout<<x*2<<'\\n';}",
    )
    assert accepted.succeeded and accepted.artifact
    run = await sandbox.run_case("cpp", b"", accepted.artifact, b"21\n", 1000, 64)
    assert run.status is SubmissionStatus.ACCEPTED
    assert run.stdout == b"42\n"

    rejected = await sandbox.compile("cpp", b"int main( { broken")
    assert rejected.succeeded is False
    assert rejected.diagnostic


@pytest.mark.asyncio
async def test_python_syntax_error_is_compile_error(sandbox: DockerSandbox) -> None:
    rejected = await sandbox.compile("python", b"def broken(:\n    pass")

    assert rejected.succeeded is False
    assert "SyntaxError" in (rejected.diagnostic or "")
