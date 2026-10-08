from __future__ import annotations

from typing import Any, Dict, List, ClassVar
import asyncio
import os
import signal
import sys
import tempfile
from contextlib import suppress

from base.agent.base_action import BaseAction

try:
    import resource
except ImportError:  # pragma: no cover - non-POSIX fallback
    resource = None


class ExecuteCodeAction(BaseAction):
    name: str = "ExecuteCodeAction"
    description: str = "Execute code in a sandboxed subprocess (python|bash). Default disabled; enable via config and whitelist."
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "code_type": {"type": "string", "enum": ["python", "bash"], "default": "python"},
            "timeout_sec": {"type": "integer", "default": 10},
        },
        "required": ["code", "code_type"],
        "additionalProperties": False,
    }

    DISALLOWED_BASH: ClassVar[List[str]] = [
        " rm ",
        "sudo",
        "chmod",
        "chown",
        ">/",
        "> /",
        " mv /",
        " dd ",
        " mkfs",
        " mount ",
    ]
    MAX_TIMEOUT_SEC: ClassVar[int] = int(os.getenv("GAIA_EXEC_MAX_TIMEOUT_SEC", "60"))
    MEMORY_LIMIT_MB: ClassVar[int] = int(os.getenv("GAIA_EXEC_MEMORY_MB", "102400"))
    MAX_OUTPUT_CHARS: ClassVar[int] = int(os.getenv("GAIA_EXEC_MAX_OUTPUT_CHARS", "40000"))
    MAX_CODE_CHARS: ClassVar[int] = int(os.getenv("GAIA_EXEC_MAX_CODE_CHARS", "200000"))
    MAX_FILE_SIZE_MB: ClassVar[int] = int(os.getenv("GAIA_EXEC_MAX_FILE_SIZE_MB", "128"))

    async def __call__(self, **kwargs) -> Any:
        code = str(kwargs.get("code", ""))
        code_type = kwargs.get("code_type", "python")
        timeout = self._normalize_timeout(kwargs.get("timeout_sec", 10))
        # Injected by benchmark environments and intentionally omitted from the
        # public action schema, so agents cannot select arbitrary host paths.
        workdir = kwargs.get("_workdir")

        if len(code) > self.MAX_CODE_CHARS:
            return {
                "success": False,
                "output": None,
                "error": f"code too large: {len(code)} chars > {self.MAX_CODE_CHARS}",
                "metrics": self._limit_metrics(timeout),
            }

        try:
            if code_type == "bash":
                return await self._exec_bash(code, timeout, workdir=workdir)
            elif code_type == "python":
                return await self._exec_python(code, timeout, workdir=workdir)
            else:
                return {"success": False, "output": None, "error": f"Unsupported code_type: {code_type}", "metrics": self._limit_metrics(timeout)}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e), "metrics": self._limit_metrics(timeout)}

    async def _exec_bash(
        self,
        code: str,
        timeout: int,
        *,
        workdir: Any = None,
    ) -> Dict[str, Any]:
        low = f" {code.strip()} ".lower()
        for bad in self.DISALLOWED_BASH:
            if bad in low:
                return {
                    "success": False,
                    "output": None,
                    "error": f"disallowed command in bash: {bad.strip()}",
                    "metrics": self._limit_metrics(timeout),
                }
        return await self._run_process(
            ["/bin/bash", "-lc", code],
            timeout,
            cwd=self._exec_dir(workdir),
        )

    async def _exec_python(
        self,
        code: str,
        timeout: int,
        *,
        workdir: Any = None,
    ) -> Dict[str, Any]:
        tmpdir = self._exec_dir(workdir)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=tmpdir, suffix=".py") as tf:
            tf.write(code)
            path = tf.name
        try:
            return await self._run_process([sys.executable, path], timeout, cwd=tmpdir)
        finally:
            with suppress(OSError):
                os.unlink(path)

    def _exec_dir(self, workdir: Any = None) -> str:
        if workdir:
            tmpdir = os.path.abspath(os.fspath(workdir))
            os.makedirs(tmpdir, exist_ok=True)
            return tmpdir
        base = os.path.abspath(os.getcwd())
        tmpdir = os.path.join(base, "workspace", ".exec")
        os.makedirs(tmpdir, exist_ok=True)
        return tmpdir

    async def _run_process(self, argv: List[str], timeout: int, cwd: str | None = None) -> Dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
            preexec_fn=self._make_preexec(timeout) if os.name == "posix" else None,
            env=self._child_env(),
            cwd=cwd,
        )

        stdout_chunks: List[bytes] = []
        stderr_chunks: List[bytes] = []
        state = {"output_bytes": 0, "stored_bytes": 0, "output_truncated": False, "kill_reason": None}
        readers = [
            asyncio.create_task(self._read_limited(proc, proc.stdout, stdout_chunks, state)),
            asyncio.create_task(self._read_limited(proc, proc.stderr, stderr_chunks, state)),
        ]

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if proc.returncode is None:
                state["kill_reason"] = "timeout"
                await self._kill_process_group(proc)
        finally:
            await asyncio.gather(*readers, return_exceptions=True)

        stdout = b"".join(stdout_chunks).decode("utf-8", "replace")
        stderr = b"".join(stderr_chunks).decode("utf-8", "replace")
        metrics = self._limit_metrics(timeout)
        metrics.update(
            {
                "returncode": proc.returncode,
                "output_bytes": state["output_bytes"],
                "output_truncated": state["output_truncated"],
            }
        )

        if state["kill_reason"] == "timeout":
            return {"success": False, "output": stdout or None, "error": "timeout", "metrics": metrics}
        if state["kill_reason"] == "output_limit":
            return {
                "success": False,
                "output": stdout or None,
                "error": f"output limit exceeded; truncated to {self.MAX_OUTPUT_CHARS} chars",
                "metrics": metrics,
            }

        ok = proc.returncode == 0
        return {"success": ok, "output": stdout, "error": None if ok else stderr, "metrics": metrics}

    async def _read_limited(
        self,
        proc: asyncio.subprocess.Process,
        stream: asyncio.StreamReader | None,
        chunks: List[bytes],
        state: Dict[str, Any],
    ) -> None:
        if stream is None:
            return
        max_bytes = self.MAX_OUTPUT_CHARS
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                return
            state["output_bytes"] += len(chunk)
            remaining = max_bytes - state["stored_bytes"]
            if remaining > 0:
                kept = chunk[:remaining]
                chunks.append(kept)
                state["stored_bytes"] += len(kept)
            if state["output_bytes"] > max_bytes:
                state["output_truncated"] = True
                if state["kill_reason"] is None:
                    state["kill_reason"] = "output_limit"
                    await self._kill_process_group(proc)
                return

    async def _kill_process_group(self, proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except Exception:
            with suppress(ProcessLookupError):
                proc.kill()
        with suppress(Exception):
            await proc.wait()

    def _make_preexec(self, timeout: int):
        def apply_limits() -> None:
            if resource is None:
                return
            cpu_limit = max(1, min(timeout + 2, self.MAX_TIMEOUT_SEC + 2))
            memory_bytes = self.MEMORY_LIMIT_MB * 1024 * 1024
            file_bytes = self.MAX_FILE_SIZE_MB * 1024 * 1024
            limits = [
                (resource.RLIMIT_CPU, cpu_limit),
                (resource.RLIMIT_AS, memory_bytes),
                (resource.RLIMIT_FSIZE, file_bytes),
                (resource.RLIMIT_CORE, 0),
                (resource.RLIMIT_NOFILE, 128),
            ]
            for limit_name, value in limits:
                with suppress(Exception):
                    resource.setrlimit(limit_name, (value, value))

        return apply_limits

    def _normalize_timeout(self, raw_timeout: Any) -> int:
        try:
            timeout = int(raw_timeout)
        except (TypeError, ValueError):
            timeout = 10
        return max(1, min(timeout, self.MAX_TIMEOUT_SEC))

    def _limit_metrics(self, timeout: int) -> Dict[str, Any]:
        return {
            "timeout_sec": timeout,
            "memory_limit_mb": self.MEMORY_LIMIT_MB,
            "max_output_chars": self.MAX_OUTPUT_CHARS,
            "max_file_size_mb": self.MAX_FILE_SIZE_MB,
        }

    def _child_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        env["MKL_NUM_THREADS"] = "1"
        env["NUMEXPR_NUM_THREADS"] = "1"
        return env
