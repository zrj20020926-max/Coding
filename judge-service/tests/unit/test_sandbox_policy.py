import pytest

from app.core.config import Settings
from app.infrastructure.sandbox import DockerSandbox


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
