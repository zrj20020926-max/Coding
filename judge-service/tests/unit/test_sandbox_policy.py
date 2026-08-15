from unittest.mock import AsyncMock, Mock

import pytest
from docker.errors import ImageNotFound

from app.core.config import Settings
from app.domain.models import SubmissionStatus
from app.errors import InfrastructureError
from app.infrastructure.sandbox import V8_COMPAT_RUNNER, DockerSandbox


class FakeDockerClient:
    pass


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_image_error_and_exception_chain_do_not_leak_image() -> None:
    client = Mock()
    client.images.get.side_effect = ImageNotFound("private.registry/runtime@sha256:secret")
    settings = Settings(_env_file=None, sandbox_pull_images=False)
    sandbox = DockerSandbox(settings, client)

    with pytest.raises(InfrastructureError) as caught:
        await sandbox._ensure_image("private.registry/runtime@sha256:secret")

    assert "private.registry" not in str(caught.value)
    assert "sha256" not in str(caught.value)
    assert caught.value.__cause__ is None


@pytest.mark.unit
def test_sandbox_policy_has_no_privileged_escape_hatches() -> None:
    settings = Settings(_env_file=None)
    sandbox = DockerSandbox(settings, FakeDockerClient())
    options = sandbox._container_options("python:3.12-alpine", ["true"], 64)

    assert options["network_mode"] == "none"
    assert options["read_only"] is True
    assert options["user"] == "65534:65534"
    assert options["cap_drop"] == ["ALL"]
    assert options["security_opt"] == ["no-new-privileges:true"]
    assert options["privileged"] is False
    assert options["pids_limit"] == settings.sandbox_pids_limit
    assert options["nano_cpus"] > 0
    assert options["mem_limit"] == options["memswap_limit"]
    assert options["oom_kill_disable"] is False
    assert set(options["tmpfs"]) == {"/workspace", "/tmp"}
    assert "size=" in options["tmpfs"]["/workspace"]
    assert "exec" in options["tmpfs"]["/workspace"]
    assert "volumes" not in options
    assert "mounts" not in options
    assert options["labels"] == {
        "codearena.role": "untrusted-sandbox",
        "codearena.environment": "local",
    }
    file_size_limit = next(
        limit for limit in options["ulimits"] if limit["Name"] == "fsize"
    )
    assert file_size_limit["Soft"] == settings.sandbox_disk_limit_bytes
    assert file_size_limit["Hard"] == settings.sandbox_disk_limit_bytes


@pytest.mark.unit
def test_runtime_wrapper_applies_output_limit_separately_from_staging_limit() -> None:
    command = DockerSandbox._wrapper("node /workspace/main.js", 64 * 1024)

    assert "ulimit -f 128" in command[-1]
    assert ">/workspace/stdout" in command[-1]


@pytest.mark.unit
def test_archive_assigns_untrusted_files_to_non_root_user() -> None:
    payload = DockerSandbox._archive({"main.py": (b"print(1)", 0o400)})
    assert payload


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["javascript-v8", "nodejs"])
async def test_javascript_modes_use_node_syntax_check(language: str) -> None:
    settings = Settings(_env_file=None)
    sandbox = DockerSandbox(settings, FakeDockerClient())
    sandbox._execute = AsyncMock(
        return_value=(None, b"", b"", 0, 1, 1024, False, False)
    )

    result = await sandbox.compile(language, b"const value = 1;")

    assert result.succeeded is True
    image, command, files, *_limits = sandbox._execute.await_args.args
    expected_image = (
        settings.sandbox_v8_image
        if language == "javascript-v8"
        else settings.sandbox_node_image
    )
    assert image == expected_image
    assert "node --check /workspace/main.js" in command[-1]
    assert files["main.js"][0] == b"const value = 1;"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_v8_runtime_injects_only_compatibility_runner() -> None:
    settings = Settings(_env_file=None)
    sandbox = DockerSandbox(settings, FakeDockerClient())
    sandbox._execute = AsyncMock(
        return_value=(None, b"3\n", b"", 0, 1, 1024, False, False)
    )

    result = await sandbox.run_case(
        "javascript-v8",
        b"const [a, b] = readline().split(' ').map(Number); print(a + b);",
        None,
        b"1 2\n",
        1000,
        64,
    )

    assert result.status is SubmissionStatus.ACCEPTED
    image, command, files, *_limits = sandbox._execute.await_args.args
    assert image == settings.sandbox_v8_image
    assert "v8-runner.cjs" in command[-1]
    assert files["v8-runner.cjs"][0] == V8_COMPAT_RUNNER
    runner = V8_COMPAT_RUNNER.decode()
    assert "readline:" in runner and "print:" in runner
    assert "cursor < input.length ? input[cursor++] : undefined" in runner
    assert "values.map(String).join(' ') + '\\n'" in runner
    assert "Object.setPrototypeOf(readline, null)" in runner
    assert "Object.setPrototypeOf(print, null)" in runner
    assert "context.process" not in runner
    assert "context.require" not in runner
    assert "context.Buffer" not in runner


@pytest.mark.unit
@pytest.mark.asyncio
async def test_node_runtime_does_not_inject_v8_runner() -> None:
    settings = Settings(_env_file=None)
    sandbox = DockerSandbox(settings, FakeDockerClient())
    sandbox._execute = AsyncMock(
        return_value=(None, b"ok\n", b"", 0, 1, 1024, False, False)
    )

    result = await sandbox.run_case(
        "nodejs",
        b"console.log(require('fs').readFileSync(0, 'utf8').trim())",
        None,
        b"ok\n",
        1000,
        64,
    )

    assert result.status is SubmissionStatus.ACCEPTED
    _image, command, files, *_limits = sandbox._execute.await_args.args
    assert "node /workspace/main.js" in command[-1]
    assert set(files) == {"main.js", "input"}


@pytest.mark.unit
def test_node_mode_misuse_gets_controlled_diagnostics_without_internal_paths() -> None:
    readline = DockerSandbox._controlled_diagnostic(
        "nodejs",
        b"ReferenceError: readline is not defined at /workspace/main.js:1:1",
        "fallback",
    )
    printing = DockerSandbox._controlled_diagnostic(
        "nodejs",
        b"ReferenceError: print is not defined at /workspace/main.js:1:1",
        "fallback",
    )

    assert readline == (
        "Node.js API error: readline() is unavailable; "
        "use fs.readFileSync(0, 'utf8')."
    )
    assert printing == (
        "Node.js API error: print() is unavailable; use console.log() "
        "or process.stdout.write()."
    )
    assert "/workspace" not in readline + printing


@pytest.mark.unit
def test_runtime_diagnostics_never_echo_internal_commands_or_images() -> None:
    diagnostic = DockerSandbox._controlled_diagnostic(
        "javascript-v8",
        b"Runtime Error: failed at /workspace/main.js node:22-bookworm-slim",
        "fallback",
    )

    assert "/workspace" not in diagnostic
    assert "node:22" not in diagnostic
