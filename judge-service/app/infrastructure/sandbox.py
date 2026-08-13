from __future__ import annotations

import asyncio
import io
import math
import secrets
import socket
import tarfile
import time
from dataclasses import dataclass
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound
from docker.types import LogConfig, Ulimit

from app.core.config import Settings
from app.domain.models import CompileResult, SubmissionStatus
from app.errors import InfrastructureError, JudgeConfigurationError

SANDBOX_UID = 65534
SANDBOX_GID = 65534
KEEPALIVE_COMMAND = ["/bin/sh", "-c", "while true; do sleep 3600; done"]
V8_COMPAT_RUNNER = b"""'use strict';
const fs = require('fs');
const vm = require('vm');

const input = fs.readFileSync(0, 'utf8').replace(/\\r\\n?/g, '\\n').split('\\n');
if (input.length && input[input.length - 1] === '') input.pop();
let cursor = 0;
const output = [];
const context = Object.create(null);
Object.assign(context, {
  readline: () => cursor < input.length ? input[cursor++] : undefined,
  print: (...values) => output.push(values.map(String).join(' ')),
});
context.globalThis = context;
Object.freeze(context);
try {
  const source = fs.readFileSync('/workspace/main.js', 'utf8');
  new vm.Script(source, { filename: 'main.js' }).runInNewContext(context);
  if (output.length) process.stdout.write(output.join('\\n') + '\\n');
} catch (error) {
  const message = error && error.stack ? error.stack : String(error);
  process.stderr.write(message + '\\n');
  process.exitCode = 1;
}
"""


@dataclass(frozen=True)
class SandboxRunResult:
    status: SubmissionStatus
    stdout: bytes
    time_used_ms: int
    memory_used_kb: int
    exit_code: int | None
    diagnostic: str | None = None


class DockerSandbox:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or docker.from_env()
        self._available_images: set[str] = set()

    async def ping(self) -> None:
        try:
            await asyncio.to_thread(self.client.ping)
        except DockerException as exc:
            raise InfrastructureError("Docker daemon is unavailable") from exc

    async def _ensure_image(self, image: str) -> None:
        if image in self._available_images:
            return
        try:
            await asyncio.to_thread(self.client.images.get, image)
        except ImageNotFound as exc:
            if not self.settings.sandbox_pull_images:
                raise InfrastructureError(f"sandbox image is not preloaded: {image}") from exc
            try:
                await asyncio.to_thread(self.client.images.pull, image)
            except DockerException as pull_exc:
                raise InfrastructureError(f"failed to pull sandbox image: {image}") from pull_exc
        except DockerException as exc:
            raise InfrastructureError("failed to inspect sandbox image") from exc
        self._available_images.add(image)

    def _container_options(self, image: str, command: list[str], memory_mb: int) -> dict[str, Any]:
        disk_bytes = self.settings.sandbox_disk_limit_bytes
        workspace_bytes = disk_bytes * 3 // 4
        tmp_bytes = disk_bytes - workspace_bytes
        memory_bytes = memory_mb * 1024 * 1024
        return {
            "image": image,
            "command": command,
            "name": f"codearena-sandbox-{secrets.token_hex(8)}",
            "detach": True,
            "network_mode": "none",
            "read_only": True,
            "user": f"{SANDBOX_UID}:{SANDBOX_GID}",
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "privileged": False,
            "pids_limit": self.settings.sandbox_pids_limit,
            "nano_cpus": self.settings.sandbox_nano_cpus,
            "mem_limit": memory_bytes,
            "memswap_limit": memory_bytes,
            "mem_swappiness": 0,
            "oom_kill_disable": False,
            "tmpfs": {
                "/workspace": (
                    f"rw,exec,nosuid,nodev,size={workspace_bytes},"
                    f"uid={SANDBOX_UID},gid={SANDBOX_GID},mode=0700"
                ),
                "/tmp": (
                    f"rw,noexec,nosuid,nodev,size={tmp_bytes},"
                    f"uid={SANDBOX_UID},gid={SANDBOX_GID},mode=0700"
                ),
            },
            "working_dir": "/workspace",
            "environment": {
                "HOME": "/workspace",
                "TMPDIR": "/tmp",
                "LANG": "C.UTF-8",
            },
            "ulimits": [
                Ulimit(name="nofile", soft=64, hard=64),
                Ulimit(
                    name="fsize",
                    soft=self.settings.sandbox_output_limit_bytes,
                    hard=self.settings.sandbox_output_limit_bytes,
                ),
            ],
            "shm_size": 1024 * 1024,
            "ipc_mode": "private",
            "stdin_open": False,
            "tty": False,
            "auto_remove": False,
            "log_config": LogConfig(type=LogConfig.types.NONE),
            "labels": {"codearena.role": "untrusted-sandbox"},
        }

    @staticmethod
    def _archive(files: dict[str, tuple[bytes, int]]) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for filename, (content, mode) in files.items():
                info = tarfile.TarInfo(filename)
                info.size = len(content)
                info.mode = mode
                info.uid = SANDBOX_UID
                info.gid = SANDBOX_GID
                info.mtime = 0
                archive.addfile(info, io.BytesIO(content))
        return buffer.getvalue()

    @staticmethod
    def _read_file(container: Any, path: str, limit: int) -> bytes:
        result = container.exec_run(
            ["/bin/cat", path],
            user=f"{SANDBOX_UID}:{SANDBOX_GID}",
            stdout=True,
            stderr=False,
        )
        if result.exit_code != 0:
            return b""
        content = result.output or b""
        return content if len(content) <= limit else b""

    def _copy_archive(self, container: Any, payload: bytes) -> bool:
        exec_id = self.client.api.exec_create(
            container.id,
            ["tar", "-x", "-C", "/workspace"],
            stdin=True,
            stdout=True,
            stderr=True,
            user=f"{SANDBOX_UID}:{SANDBOX_GID}",
        )["Id"]
        stream = self.client.api.exec_start(exec_id, socket=True, tty=False)
        raw_socket = getattr(stream, "_sock", stream)
        try:
            raw_socket.sendall(payload)
            raw_socket.shutdown(socket.SHUT_WR)
            while raw_socket.recv(4096):
                pass
        finally:
            stream.close()
        inspection = self.client.api.exec_inspect(exec_id)
        return inspection.get("ExitCode") == 0

    @staticmethod
    def _state(container: Any) -> dict[str, Any]:
        try:
            container.reload()
            return container.attrs.get("State", {})
        except DockerException:
            return {}

    @staticmethod
    def _memory_used_kb(container: Any) -> int:
        try:
            stats = container.stats(stream=False)
            memory = stats.get("memory_stats", {})
            peak = memory.get("max_usage") or memory.get("usage") or 0
            return max(0, int(peak) // 1024)
        except DockerException:
            return 0

    async def _execute(
        self,
        image: str,
        command: list[str],
        files: dict[str, tuple[bytes, int]],
        timeout_seconds: float,
        memory_mb: int,
    ) -> tuple[Any, bytes, bytes, int | None, int, int, bool, bool]:
        await self._ensure_image(image)
        container = None
        started = time.monotonic()
        timed_out = False
        try:
            try:
                options = self._container_options(image, KEEPALIVE_COMMAND, memory_mb)
                container = await asyncio.to_thread(self.client.containers.create, **options)
                await asyncio.to_thread(container.start)
                payload = self._archive(files)
                copied = await asyncio.to_thread(self._copy_archive, container, payload)
                if not copied:
                    raise InfrastructureError("Docker rejected sandbox input archive")
                started = time.monotonic()
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(
                            container.exec_run,
                            command,
                            user=f"{SANDBOX_UID}:{SANDBOX_GID}",
                            stdout=True,
                            stderr=True,
                        ),
                        timeout=timeout_seconds,
                    )
                except TimeoutError:
                    timed_out = True
                    await asyncio.to_thread(container.kill)
            except InfrastructureError:
                raise
            except DockerException as exc:
                raise InfrastructureError("Docker sandbox execution failed") from exc

            elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
            state = await asyncio.to_thread(self._state, container)
            oom_killed = bool(state.get("OOMKilled"))
            memory_used_kb = await asyncio.to_thread(self._memory_used_kb, container)
            if timed_out:
                return container, b"", b"", None, elapsed_ms, memory_used_kb, True, oom_killed

            output_limit = self.settings.sandbox_output_limit_bytes
            stdout = await asyncio.to_thread(
                self._read_file, container, "/workspace/stdout", output_limit + 1
            )
            stderr = await asyncio.to_thread(
                self._read_file, container, "/workspace/stderr", output_limit + 1
            )
            exit_raw = await asyncio.to_thread(
                self._read_file, container, "/workspace/exit_code", 32
            )
            try:
                exit_code = int(exit_raw.decode().strip())
            except (UnicodeDecodeError, ValueError):
                exit_code = state.get("ExitCode")
            return (
                container,
                stdout,
                stderr,
                exit_code,
                elapsed_ms,
                memory_used_kb,
                False,
                oom_killed,
            )
        finally:
            if container is not None:
                try:
                    await asyncio.to_thread(container.remove, force=True, v=True)
                except DockerException:
                    pass

    @staticmethod
    def _wrapper(program: str, output_limit: int) -> list[str]:
        file_blocks = max(1, math.ceil(output_limit / 512))
        script = (
            "set +e; "
            f"ulimit -f {file_blocks}; "
            f"{program} </workspace/input >/workspace/stdout 2>/workspace/stderr; "
            "code=$?; printf '%s' \"$code\" >/workspace/exit_code; exit 0"
        )
        return ["/bin/sh", "-c", script]

    async def _compile_cpp_with_artifact(self, source: bytes) -> CompileResult:
        await self._ensure_image(self.settings.sandbox_cpp_image)
        container = None
        try:
            command = self._wrapper(
                "g++ -O2 -pipe -std=c++20 -o /workspace/app /workspace/main.cpp",
                self.settings.sandbox_output_limit_bytes,
            )
            options = self._container_options(
                self.settings.sandbox_cpp_image,
                KEEPALIVE_COMMAND,
                self.settings.sandbox_compile_memory_mb,
            )
            container = await asyncio.to_thread(self.client.containers.create, **options)
            await asyncio.to_thread(container.start)
            payload = self._archive(
                {
                    "main.cpp": (source, 0o400),
                    "input": (b"", 0o400),
                }
            )
            if not await asyncio.to_thread(self._copy_archive, container, payload):
                raise InfrastructureError("Docker rejected compiler input archive")
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        container.exec_run,
                        command,
                        user=f"{SANDBOX_UID}:{SANDBOX_GID}",
                        stdout=True,
                        stderr=True,
                    ),
                    timeout=self.settings.sandbox_compile_timeout_seconds,
                )
            except TimeoutError:
                await asyncio.to_thread(container.kill)
                return CompileResult(False, diagnostic="compilation wall-clock limit exceeded")
            state = await asyncio.to_thread(self._state, container)
            if state.get("OOMKilled"):
                return CompileResult(False, diagnostic="compiler memory limit exceeded")
            exit_raw = await asyncio.to_thread(
                self._read_file, container, "/workspace/exit_code", 32
            )
            exit_code = int(exit_raw.decode().strip() or "-1")
            if exit_code != 0:
                stderr = await asyncio.to_thread(
                    self._read_file,
                    container,
                    "/workspace/stderr",
                    self.settings.sandbox_output_limit_bytes + 1,
                )
                diagnostic = stderr[:16_384].decode("utf-8", errors="replace")
                return CompileResult(False, diagnostic=diagnostic or "compilation failed")
            artifact = await asyncio.to_thread(
                self._read_file,
                container,
                "/workspace/app",
                self.settings.sandbox_disk_limit_bytes,
            )
            if not artifact:
                raise InfrastructureError("compiler produced no executable artifact")
            return CompileResult(True, artifact=artifact)
        except InfrastructureError:
            raise
        except (DockerException, UnicodeDecodeError, ValueError) as exc:
            raise InfrastructureError("Docker compilation failed") from exc
        finally:
            if container is not None:
                try:
                    await asyncio.to_thread(container.remove, force=True, v=True)
                except DockerException:
                    pass

    async def _compile_python(self, source: bytes) -> CompileResult:
        command = self._wrapper(
            "python -I -m py_compile /workspace/main.py",
            self.settings.sandbox_output_limit_bytes,
        )
        (
            _container,
            _stdout,
            stderr,
            exit_code,
            _elapsed_ms,
            _memory_used_kb,
            timed_out,
            oom_killed,
        ) = await self._execute(
            self.settings.sandbox_python_image,
            command,
            {
                "main.py": (source, 0o400),
                "input": (b"", 0o400),
            },
            self.settings.sandbox_compile_timeout_seconds,
            self.settings.sandbox_compile_memory_mb,
        )
        if timed_out:
            return CompileResult(False, diagnostic="compilation wall-clock limit exceeded")
        if oom_killed or exit_code == 137:
            return CompileResult(False, diagnostic="compiler memory limit exceeded")
        if exit_code != 0:
            diagnostic = stderr[:16_384].decode("utf-8", errors="replace")
            return CompileResult(False, diagnostic=diagnostic or "compilation failed")
        return CompileResult(True)

    async def compile(self, language: str, source: bytes) -> CompileResult:
        if language == "python":
            return await self._compile_python(source)
        if language == "cpp":
            return await self._compile_cpp_with_artifact(source)
        if language in {"javascript-v8", "nodejs"}:
            return await self._compile_javascript(source)
        raise JudgeConfigurationError(f"unsupported language: {language}")

    async def _compile_javascript(self, source: bytes) -> CompileResult:
        command = self._wrapper(
            "node --check /workspace/main.js",
            self.settings.sandbox_output_limit_bytes,
        )
        (
            _container,
            _stdout,
            stderr,
            exit_code,
            _elapsed_ms,
            _memory_used_kb,
            timed_out,
            oom_killed,
        ) = await self._execute(
            self.settings.sandbox_node_image,
            command,
            {"main.js": (source, 0o400), "input": (b"", 0o400)},
            self.settings.sandbox_compile_timeout_seconds,
            self.settings.sandbox_compile_memory_mb,
        )
        if timed_out:
            return CompileResult(False, diagnostic="syntax check wall-clock limit exceeded")
        if oom_killed or exit_code == 137:
            return CompileResult(False, diagnostic="syntax check memory limit exceeded")
        if exit_code != 0:
            diagnostic = stderr[:16_384].decode("utf-8", errors="replace")
            return CompileResult(False, diagnostic=diagnostic or "JavaScript syntax error")
        return CompileResult(True)

    async def run_case(
        self,
        language: str,
        source: bytes,
        artifact: bytes | None,
        stdin: bytes,
        time_limit_ms: int,
        memory_limit_mb: int,
    ) -> SandboxRunResult:
        if language == "python":
            image = self.settings.sandbox_python_image
            program = "python -I /workspace/main.py"
            files = {"main.py": (source, 0o400), "input": (stdin, 0o400)}
        elif language == "cpp" and artifact is not None:
            image = self.settings.sandbox_cpp_image
            program = "/workspace/app"
            files = {"app": (artifact, 0o500), "input": (stdin, 0o400)}
        elif language == "nodejs":
            image = self.settings.sandbox_node_image
            program = "node /workspace/main.js"
            files = {"main.js": (source, 0o400), "input": (stdin, 0o400)}
        elif language == "javascript-v8":
            image = self.settings.sandbox_node_image
            program = "node --no-warnings /workspace/v8-runner.cjs"
            files = {
                "main.js": (source, 0o400),
                "v8-runner.cjs": (V8_COMPAT_RUNNER, 0o400),
                "input": (stdin, 0o400),
            }
        else:
            raise JudgeConfigurationError(f"invalid runtime configuration: {language}")

        command = self._wrapper(program, self.settings.sandbox_output_limit_bytes)
        (
            _container,
            stdout,
            stderr,
            exit_code,
            elapsed_ms,
            memory_used_kb,
            timed_out,
            oom_killed,
        ) = await self._execute(
            image,
            command,
            files,
            max(0.1, time_limit_ms / 1000),
            memory_limit_mb,
        )
        if timed_out:
            return SandboxRunResult(
                SubmissionStatus.TIME_LIMIT_EXCEEDED,
                b"",
                elapsed_ms,
                memory_used_kb,
                None,
                "wall-clock limit exceeded",
            )
        if oom_killed:
            return SandboxRunResult(
                SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
                b"",
                elapsed_ms,
                memory_used_kb,
                exit_code,
                "memory limit exceeded",
            )
        if exit_code == 137:
            return SandboxRunResult(
                SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
                b"",
                elapsed_ms,
                memory_used_kb,
                exit_code,
                "process was killed at the configured memory limit",
            )
        output_limit = self.settings.sandbox_output_limit_bytes
        if (
            len(stdout) >= output_limit
            or len(stderr) >= output_limit
            or exit_code == 153
            or b"File too large" in stderr
        ):
            return SandboxRunResult(
                SubmissionStatus.OUTPUT_LIMIT_EXCEEDED,
                b"",
                elapsed_ms,
                memory_used_kb,
                exit_code,
                "output limit exceeded",
            )
        if exit_code != 0 and (
            b"MemoryError" in stderr or b"std::bad_alloc" in stderr
        ):
            return SandboxRunResult(
                SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
                b"",
                elapsed_ms,
                memory_used_kb,
                exit_code,
                "memory allocation failed at the configured limit",
            )
        if exit_code != 0:
            diagnostic = stderr[:4096].decode("utf-8", errors="replace")
            return SandboxRunResult(
                SubmissionStatus.RUNTIME_ERROR,
                stdout,
                elapsed_ms,
                memory_used_kb,
                exit_code,
                diagnostic or "process exited with a non-zero status",
            )
        return SandboxRunResult(
            SubmissionStatus.ACCEPTED,
            stdout,
            elapsed_ms,
            memory_used_kb,
            exit_code,
        )
