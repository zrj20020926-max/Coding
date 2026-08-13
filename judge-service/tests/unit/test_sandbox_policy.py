from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.domain.models import SubmissionStatus
from app.infrastructure.sandbox import V8_COMPAT_RUNNER, DockerSandbox


class FakeDockerClient:
    pass


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
    assert image == settings.sandbox_node_image
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
    assert image == settings.sandbox_node_image
    assert "v8-runner.cjs" in command[-1]
    assert files["v8-runner.cjs"][0] == V8_COMPAT_RUNNER
    runner = V8_COMPAT_RUNNER.decode()
    assert "readline:" in runner and "print:" in runner
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
