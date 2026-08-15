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


async def run(
    sandbox: DockerSandbox,
    language: str,
    source: bytes,
    stdin: bytes = b"",
    *,
    timeout_ms: int = 1000,
    memory_mb: int = 64,
):
    compiled = await sandbox.compile(language, source)
    assert compiled.succeeded, compiled.diagnostic
    return await sandbox.run_case(
        language,
        source,
        compiled.artifact,
        stdin,
        timeout_ms,
        memory_mb,
    )


@pytest.mark.asyncio
async def test_v8_readline_print_eof_and_modern_javascript(
    sandbox: DockerSandbox,
) -> None:
    source = b"""\
const first = readline();
const second = readline();
const eof = readline();
const values = new Map([['a', 2n], ['b', 3n]]);
const unique = new Set([first, second, first]);
print(first);
print(second, eof === undefined, values.get('a') + values.get('b'), unique.size);
"""
    result = await run(sandbox, "javascript-v8", source, b"alpha\nbeta\n")

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == b"alpha\nbeta true 5 2\n"


@pytest.mark.asyncio
async def test_v8_preserves_empty_lines_and_normalizes_crlf(
    sandbox: DockerSandbox,
) -> None:
    source = b"print(JSON.stringify([readline(), readline(), readline(), readline()]));"
    result = await run(sandbox, "javascript-v8", source, b"one\r\n\r\nthree\r\n")

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == b'["one","","three",null]\n'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "message"),
    [
        (b"require('fs')", "require is unavailable"),
        (b"process.stdout.write('unsafe')", "process is unavailable"),
        (b"print(Buffer.from('unsafe'))", "Buffer is unavailable"),
    ],
)
async def test_v8_rejects_node_apis_with_controlled_diagnostics(
    sandbox: DockerSandbox,
    source: bytes,
    message: str,
) -> None:
    result = await run(sandbox, "javascript-v8", source)

    assert result.status is SubmissionStatus.RUNTIME_ERROR
    assert result.diagnostic is not None and message in result.diagnostic
    assert "/workspace" not in result.diagnostic
    assert "node:22" not in result.diagnostic


@pytest.mark.asyncio
async def test_v8_has_no_network_or_host_constructor_escape(
    sandbox: DockerSandbox,
) -> None:
    source = b"""\
let escaped = false;
try { readline.constructor('return process')(); escaped = true; } catch (_) {}
print(typeof fetch, typeof WebSocket, typeof XMLHttpRequest, typeof process, escaped);
"""
    result = await run(sandbox, "javascript-v8", source)

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == b"undefined undefined undefined undefined false\n"


@pytest.mark.asyncio
async def test_node_stdin_console_stdout_and_standard_apis(
    sandbox: DockerSandbox,
) -> None:
    source = b"""\
const fs = require('fs');
const input = fs.readFileSync(0, 'utf8');
const values = new Map([['value', 40n]]);
const set = new Set([1, 1, 2]);
const buffer = Buffer.from(input, 'utf8');
console.log(values.get('value') + 2n, set.size, buffer.length);
process.stdout.write(input);
"""
    result = await run(sandbox, "nodejs", source, "你好\n".encode())

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == "42n 2 7\n你好\n".encode()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stdin", "expected"),
    [
        (b"", b"empty\n"),
        (b"a\n\nb\n", b"a||b|\n"),
        (b"a\r\n\r\nb\r\n", b"crlf\n"),
        ("汉字🙂\n".encode(), "汉字🙂\n".encode()),
    ],
)
async def test_node_preserves_raw_stdin_forms(
    sandbox: DockerSandbox,
    stdin: bytes,
    expected: bytes,
) -> None:
    source = b"""\
const fs = require('fs');
const input = fs.readFileSync(0, 'utf8');
if (input === '') console.log('empty');
else if (input.includes('\\r\\n')) console.log('crlf');
else if (input === 'a\\n\\nb\\n') console.log(input.split('\\n').join('|'));
else process.stdout.write(input);
"""
    result = await run(sandbox, "nodejs", source, stdin)

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "source"),
    [
        ("javascript-v8", b"print(readline().length);"),
        (
            "nodejs",
            b"console.log(require('fs').readFileSync(0, 'utf8').trimEnd().length);",
        ),
    ],
)
async def test_input_may_exceed_output_limit(
    sandbox: DockerSandbox,
    language: str,
    source: bytes,
) -> None:
    stdin = b"x" * (128 * 1024) + b"\n"

    result = await run(sandbox, language, source, stdin, timeout_ms=2000)

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == b"131072\n"


@pytest.mark.asyncio
async def test_node_network_sensitive_file_and_root_write_are_blocked(
    sandbox: DockerSandbox,
) -> None:
    source = b"""\
const fs = require('fs');
const net = require('net');
let blocked = 0;
try { fs.readFileSync('/etc/shadow'); } catch (_) { blocked += 1; }
try { fs.writeFileSync('/codearena-forbidden', 'x'); } catch (_) { blocked += 1; }
const socket = net.createConnection({ host: '1.1.1.1', port: 53 });
socket.setTimeout(200);
socket.on('connect', () => { socket.destroy(); console.log('unsafe'); });
socket.on('error', () => { blocked += 1; console.log(blocked === 3 ? 'blocked' : 'unsafe'); });
socket.on('timeout', () => {
  blocked += 1;
  socket.destroy();
  console.log(blocked === 3 ? 'blocked' : 'unsafe');
});
"""
    result = await run(sandbox, "nodejs", source, timeout_ms=1500)

    assert result.status is SubmissionStatus.ACCEPTED
    assert result.stdout == b"blocked\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "source", "message"),
    [
        ("nodejs", b"readline()", "readline() is unavailable"),
        ("nodejs", b"print('x')", "print() is unavailable"),
        ("javascript-v8", b"require('fs')", "require is unavailable"),
    ],
)
async def test_runtime_modes_cannot_be_mixed(
    sandbox: DockerSandbox,
    language: str,
    source: bytes,
    message: str,
) -> None:
    result = await run(sandbox, language, source)

    assert result.status is SubmissionStatus.RUNTIME_ERROR
    assert result.diagnostic is not None and message in result.diagnostic


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["javascript-v8", "nodejs"])
async def test_dead_loop_is_killed_by_wall_clock_limit(
    sandbox: DockerSandbox,
    language: str,
) -> None:
    result = await run(sandbox, language, b"while (true) {}", timeout_ms=200)
    assert result.status is SubmissionStatus.TIME_LIMIT_EXCEEDED


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["javascript-v8", "nodejs"])
async def test_memory_explosion_is_classified(
    sandbox: DockerSandbox,
    language: str,
) -> None:
    source = b"const a=[]; while (true) a.push(new Array(250000).fill(1));"
    result = await run(sandbox, language, source, timeout_ms=5000)
    assert result.status is SubmissionStatus.MEMORY_LIMIT_EXCEEDED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "source"),
    [
        ("javascript-v8", b"while (true) print('x'.repeat(1024));"),
        ("nodejs", b"while (true) console.log('x'.repeat(1024));"),
    ],
)
async def test_excessive_output_is_stopped(
    sandbox: DockerSandbox,
    language: str,
    source: bytes,
) -> None:
    result = await run(sandbox, language, source, timeout_ms=2000)
    assert result.status is SubmissionStatus.OUTPUT_LIMIT_EXCEEDED
    assert result.diagnostic == "output limit exceeded"


@pytest.mark.asyncio
async def test_node_child_processes_are_bounded_by_pid_limit(
    sandbox: DockerSandbox,
) -> None:
    source = (
        b"const {spawn}=require('child_process'); while(true) "
        b"spawn(process.execPath,['-e','setInterval(()=>{},1000)']);"
    )
    result = await run(sandbox, "nodejs", source, timeout_ms=2000)

    assert result.status in {
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.TIME_LIMIT_EXCEEDED,
        SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
    }


@pytest.mark.asyncio
async def test_node_cannot_fill_temporary_storage_beyond_file_limit(
    sandbox: DockerSandbox,
) -> None:
    source = b"require('fs').writeFileSync('/tmp/fill', Buffer.alloc(2 * 1024 * 1024));"
    result = await run(sandbox, "nodejs", source, timeout_ms=2000)

    assert result.status in {
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.OUTPUT_LIMIT_EXCEEDED,
    }


@pytest.mark.asyncio
async def test_v8_cannot_access_files_or_spawn_children(
    sandbox: DockerSandbox,
) -> None:
    source = b"require('child_process').spawn('sh');"
    result = await run(sandbox, "javascript-v8", source)

    assert result.status is SubmissionStatus.RUNTIME_ERROR
    assert result.diagnostic is not None and "require is unavailable" in result.diagnostic


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["javascript-v8", "nodejs"])
async def test_javascript_syntax_error_is_compile_error(
    sandbox: DockerSandbox,
    language: str,
) -> None:
    rejected = await sandbox.compile(language, b"const broken = ;")
    assert rejected.succeeded is False
    assert rejected.diagnostic
    assert "/workspace" not in rejected.diagnostic
    assert "node:22" not in rejected.diagnostic
