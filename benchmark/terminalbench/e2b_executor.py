"""
E2B executor for Terminal Bench tasks using SDK-based approach.

Uses e2b SDK directly instead of CLI for template building.
"""
import asyncio
import os
from pathlib import Path
from typing import Optional, Tuple, Set, Callable, TypeVar

from dirhash import dirhash
from e2b import (
    AsyncSandbox,
    AsyncTemplate,
    TemplateBase,
    LogEntry,
    BuildInfo,
)
from e2b.sandbox.filesystem.filesystem import WriteEntry
import httpx
import httpcore

from base.engine.logs import logger
from benchmark.terminalbench.base_executor import BaseExecutor


DEFAULT_SANDBOX_TIMEOUT = 3600  # E2B max timeout is 1 hour
MAX_RETRIES = 3
RETRY_DELAY = 3

# Global state for sandbox tracking and template locking
_active_sandboxes: Set[str] = set()
_template_locks: dict = {}

T = TypeVar('T')


def _is_network_error(exc: Exception) -> bool:
    """Check if exception is a retryable network error."""
    return isinstance(exc, (
        httpx.ReadError, httpx.ConnectError, httpx.TimeoutException,
        httpcore.ReadError, httpcore.ConnectError,
        ConnectionError, TimeoutError, asyncio.TimeoutError,
    ))


async def _retry_async(
    fn: Callable[[], T],
    operation: str,
    retries: int = MAX_RETRIES,
    delay: int = RETRY_DELAY,
    on_retry: Callable[[], None] = None,
) -> T:
    """Generic async retry wrapper for network-prone operations."""
    last_error = None
    for attempt in range(retries):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            logger.error(f"{operation} failed (attempt {attempt + 1}/{retries})")
            logger.error(f"  Error type: {type(e).__name__}")
            logger.error(f"  Error message: {str(e)}")
            if hasattr(e, '__dict__'):
                logger.error(f"  Error details: {e.__dict__}")
            
            if _is_network_error(e) and attempt < retries - 1:
                logger.warning(f"  Retrying in {delay}s...")
                if on_retry:
                    await on_retry() if asyncio.iscoroutinefunction(on_retry) else on_retry()
                await asyncio.sleep(delay)
            else:
                raise
    raise RuntimeError(f"{operation} failed after {retries} attempts: {last_error}")


async def cleanup_all_sandboxes():
    """Clean up all tracked sandboxes on program exit."""
    if not _active_sandboxes:
        return
    
    sandboxes = list(_active_sandboxes)
    logger.warning(f"Cleaning up {len(sandboxes)} remaining sandbox(es)")
    
    for sandbox_id in sandboxes:
        try:
            sandbox = await asyncio.wait_for(AsyncSandbox.connect(sandbox_id), timeout=5)
            await asyncio.wait_for(sandbox.kill(), timeout=10)
            logger.info(f"Cleaned up orphaned sandbox {sandbox_id}")
        except Exception as e:
            if "404" not in str(e).lower():
                logger.debug(f"Cleanup failed for {sandbox_id}: {e}")
        finally:
            _active_sandboxes.discard(sandbox_id)


class E2BExecutor(BaseExecutor):
    """Executes Terminal Bench tasks in E2B sandboxes using SDK."""

    def __init__(
        self,
        task_id: str,
        task_dir: Path,
        task_config: dict,
        verifier_logs_dir: Path,
        agent_logs_dir: Path,
        timeout: int = 600,
        env_init: Optional[dict[str, str]] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(task_id, task_dir, task_config, verifier_logs_dir, agent_logs_dir, timeout, env_init)
        self.sandbox: Optional[AsyncSandbox] = None
        self.sandbox_id: Optional[str] = None
        self._api_key = api_key

        if api_key:
            os.environ["E2B_API_KEY"] = api_key

        self.environment_dir = task_dir / "environment"
        self._dockerfile_path = self.environment_dir / "Dockerfile"

        # Generate deterministic template name based on task_id, environment hash, and API key
        # This ensures templates are unique per team/account
        env_hash = dirhash(self.environment_dir, "sha256")[:12]
        # Include API key hash to avoid cross-team template conflicts
        key_hash = ""
        if self._api_key:
            import hashlib
            key_hash = hashlib.sha256(self._api_key.encode()).hexdigest()[:6]
        prefix = f"dw-{key_hash}" if key_hash else "dw-local"
        self.template_name = f"{prefix}-{task_id}-{env_hash}".replace(".", "-").replace("_", "-").lower()
        self.workdir = self._extract_workdir()
        
        logger.debug(f"E2B executor: template={self.template_name}, workdir={self.workdir}")

    def _extract_workdir(self) -> Optional[str]:
        """Extract WORKDIR from Dockerfile."""
        if not self._dockerfile_path.exists():
            return None
        try:
            for line in reversed(self._dockerfile_path.read_text().splitlines()):
                parts = line.strip().split(maxsplit=1)
                if parts and parts[0].upper() == "WORKDIR" and len(parts) == 2:
                    return parts[1]
        except Exception:
            pass
        return None

    async def _check_template_exists(self) -> bool:
        """Check if template alias already exists using SDK."""
        try:
            exists = await AsyncTemplate.alias_exists(
                self.template_name,
                api_key=self._api_key,
            )
            if exists:
                logger.info(f"Template '{self.template_name}' already exists, skipping build")
            else:
                logger.debug(f"Template '{self.template_name}' not found, will build")
            return exists
        except Exception as e:
            logger.debug(f"Template check failed: {e}")
            return False

    def _parse_memory_to_mb(self, memory_str: str) -> int:
        """Parse memory string (e.g., '2G', '512M') to MB."""
        memory_str = memory_str.strip().upper()
        if memory_str.endswith('G'):
            return int(float(memory_str[:-1]) * 1024)
        elif memory_str.endswith('M'):
            return int(float(memory_str[:-1]))
        else:
            return int(memory_str)

    def _build_log_callback(self, log_entry: LogEntry) -> None:
        """Callback for build logs."""
        level = getattr(log_entry, 'level', 'info')
        message = getattr(log_entry, 'message', str(log_entry))
        logger.info(f"[E2B Build] [{level}] {message}")

    async def _build_template(self) -> None:
        """Build E2B template from Dockerfile using SDK."""
        if not self._dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found: {self._dockerfile_path}")

        # Read resource configuration from task.toml
        env_config = self.task_config.get("environment", {})
        cpu_count = env_config.get("cpus", 2)
        memory_str = env_config.get("memory", "512M")
        memory_mb = self._parse_memory_to_mb(memory_str)
        
        logger.info(f"Building template {self.template_name}")
        logger.info(f"  Environment dir: {self.environment_dir}")
        logger.info(f"  Dockerfile: {self._dockerfile_path}")
        logger.info(f"  Resources: {cpu_count} CPUs, {memory_mb} MB memory")
        
        # Fix Dockerfile for E2B compatibility and add Claude CLI
        fixed_dockerfile = self.environment_dir / "Dockerfile.e2b"
        original_content = self._dockerfile_path.read_text()
        
        lines = original_content.splitlines()
        fixed_lines = []
        
        for line in lines:
            stripped = line.strip()
            fixed_lines.append(line)
            
            # After FROM instruction, add Node.js and Claude CLI installation
            if stripped.upper().startswith('FROM ') and 'AS ' not in stripped.upper():
                fixed_lines.append('# Ensure /app directory exists')
                fixed_lines.append('RUN mkdir -p /app')
                fixed_lines.append('')
                fixed_lines.append('# Install Node.js and Claude CLI for ClaudeCodeAgent')
                fixed_lines.append('RUN apt-get update && \\')
                fixed_lines.append('    apt-get install -y curl ca-certificates gnupg && \\')
                fixed_lines.append('    mkdir -p /etc/apt/keyrings && \\')
                fixed_lines.append('    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \\')
                fixed_lines.append('    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \\')
                fixed_lines.append('    apt-get update && \\')
                fixed_lines.append('    apt-get install -y nodejs && \\')
                fixed_lines.append('    npm install -g npm@latest && \\')
                fixed_lines.append('    apt-get clean && rm -rf /var/lib/apt/lists/*')
                fixed_lines.append('')
                fixed_lines.append('# Install Claude CLI globally')
                fixed_lines.append('RUN export HOME=/root && \\')
                fixed_lines.append('    curl -fsSL https://claude.ai/install.sh | bash && \\')
                fixed_lines.append('    if [ -f "/root/.local/bin/claude" ]; then cp /root/.local/bin/claude /usr/local/bin/claude && chmod 755 /usr/local/bin/claude; fi && \\')
                fixed_lines.append('    if [ -d "/root/.claude" ]; then cp -r /root/.claude /opt/claude && chmod -R 755 /opt/claude; fi')
        
        fixed_content = '\n'.join(fixed_lines)
        fixed_dockerfile.write_text(fixed_content, encoding='utf-8')
        logger.info(f"  Created E2B-compatible Dockerfile with Node.js and Claude CLI")
        
        try:
            async def do_build():
                # Use SDK to parse Dockerfile and build template
                template = TemplateBase(
                    file_context_path=str(self.environment_dir)
                ).from_dockerfile(str(fixed_dockerfile))
                
                try:
                    # Build using AsyncTemplate.build()
                    build_info: BuildInfo = await AsyncTemplate.build(
                        template=template,
                        alias=self.template_name,
                        cpu_count=cpu_count,
                        memory_mb=memory_mb,
                        skip_cache=False,
                        on_build_logs=self._build_log_callback,
                        api_key=self._api_key,
                    )
                    
                    logger.info(f"Template {self.template_name} built successfully")
                    logger.info(f"  Template ID: {build_info.template_id}")
                    logger.info(f"  Build ID: {build_info.build_id}")
                except Exception as build_error:
                    # Handle "alias already taken" error - template already exists
                    error_msg = str(build_error).lower()
                    if "alias" in error_msg and "already taken" in error_msg:
                        logger.info(f"Template {self.template_name} already exists (alias taken), skipping build")
                        return  # Template exists, no need to rebuild
                    raise  # Re-raise other errors
            
            await _retry_async(do_build, f"Build template {self.template_name}")
        
        finally:
            # Clean up temporary Dockerfile
            if fixed_dockerfile.exists():
                try:
                    fixed_dockerfile.unlink()
                    logger.debug(f"Removed temporary Dockerfile")
                except Exception as e:
                    logger.warning(f"Failed to remove temp Dockerfile: {e}")

    async def _create_sandbox(self) -> None:
        """Create sandbox from template."""
        timeout = int(os.environ.get("E2B_SANDBOX_TIMEOUT", DEFAULT_SANDBOX_TIMEOUT))

        async def do_create():
            logger.info(f"Creating sandbox from {self.template_name}")
            self.sandbox = await asyncio.wait_for(
                AsyncSandbox.create(
                    template=self.template_name,
                    metadata={"task_id": self.task_id},
                    timeout=timeout,
                ),
                timeout=120
            )
            self.sandbox_id = self.sandbox.sandbox_id
            _active_sandboxes.add(self.sandbox_id)
            logger.info(f"Sandbox created: {self.sandbox_id}")

        await _retry_async(do_create, "Create sandbox", on_retry=self._cleanup_partial)

    async def _cleanup_partial(self) -> None:
        """Clean up partially created sandbox."""
        if self.sandbox:
            try:
                await asyncio.wait_for(self.sandbox.kill(), timeout=10)
            except Exception:
                pass
        if self.sandbox_id:
            _active_sandboxes.discard(self.sandbox_id)
        self.sandbox = None
        self.sandbox_id = None

    async def _setup_directories(self) -> None:
        """Create required directories in sandbox."""
        async def do_setup():
            await asyncio.wait_for(self.sandbox.files.make_dir("/logs/agent"), timeout=15)
            await asyncio.wait_for(self.sandbox.files.make_dir("/logs/verifier"), timeout=15)

        await _retry_async(do_setup, "Setup directories", delay=2)

    async def _install_claude_cli(self) -> None:
        """Verify Claude Code CLI is installed in the sandbox.
        
        The CLI should already be installed via Dockerfile.
        This method just validates the installation.
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not started")

        logger.info("Verifying Claude CLI installation...")
        
        # Check if Claude CLI is available (as regular user, since that's who will run it)
        verify_output, verify_code = await self.execute_command(
            "bash -lc 'command -v claude >/dev/null 2>&1 && claude --version 2>&1 || echo NOT_INSTALLED'", 
            timeout=10,
            user="user"
        )
        
        if verify_code == 0 and "NOT_INSTALLED" not in verify_output:
            logger.info(f"✓ Claude CLI is available: {verify_output.strip()}")
        else:
            # Try to add to PATH if installed in ~/.local/bin
            logger.info("Attempting to fix PATH for Claude CLI...")
            fix_result, _ = await self.execute_command(
                "bash -c 'export PATH=\"$HOME/.local/bin:$PATH\" && command -v claude && claude --version'",
                timeout=10,
                user="user"
            )
            if "Claude Code" in fix_result:
                logger.info(f"✓ Claude CLI found after PATH fix: {fix_result.strip()}")
            else:
                logger.warning(
                    "⚠ Claude CLI not accessible. "
                    "It should have been installed via Dockerfile. "
                    "ClaudeCodeAgent may not work properly."
                )

    async def start_container(self, force_build: bool = False) -> None:
        """Start the E2B sandbox container."""
        if self.template_name not in _template_locks:
            _template_locks[self.template_name] = asyncio.Lock()
        
        try:
            async with _template_locks[self.template_name]:
                if force_build or not await self._check_template_exists():
                    await self._build_template()
            
            await self._create_sandbox()
            await self._setup_directories()
            await self._install_claude_cli()
            logger.info(f"Container ready for task {self.task_id}")
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to start container for {self.task_id}: {type(e).__name__}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            await self.cleanup()
            raise

    async def execute_command(self, command: str, timeout: Optional[int] = None, user: str = None) -> Tuple[str, int]:
        """Execute a command in the sandbox.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            user: User to run as (default: "user" for non-root, can override to "root")
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not started")

        cmd_timeout = timeout or self.timeout
        run_as_user = user if user is not None else "user"  # Default to non-root

        try:
            handle = await asyncio.wait_for(
                self.sandbox.commands.run(
                    cmd=command, background=True, cwd=self.workdir,
                    timeout=cmd_timeout, user=run_as_user,
                ),
                timeout=cmd_timeout + 10
            )
            result = await asyncio.wait_for(handle.wait(), timeout=cmd_timeout + 10)
            logger.info(f"Command result: exit_code={result.exit_code}")
            
            # Combine stdout and stderr for complete output
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            
            return output, result.exit_code
            
        except asyncio.TimeoutError:
            logger.error(f"Command timeout ({cmd_timeout}s): {command[:100]}")
            return f"Command timeout after {cmd_timeout} seconds", 124
        except Exception as e:
            logger.error(f"Command error: {e}")
            return f"Command exited with code 1 and error:\n{str(e)}", 1

    async def run_tests(self) -> float:
        """Run tests and return reward."""
        if not self.sandbox:
            raise RuntimeError("Sandbox not started")

        test_script = self.task_dir / "tests" / "test.sh"
        if not test_script.exists():
            logger.error(f"Test script not found: {test_script}")
            self._save_verifier_result("", 0.0, error="Test script not found")
            return 0.0

        output = ""
        reward = 0.0
        error_msg = None

        try:
            # Upload test files
            tests_dir = self.task_dir / "tests"
            files = [
                WriteEntry(path=f"/tests/{f.relative_to(tests_dir)}", data=f.read_bytes())
                for f in tests_dir.rglob("*") if f.is_file()
            ]
            if files:
                await self.sandbox.files.write_files(files)
                logger.info(f"Uploaded {len(files)} test files")

            await self.execute_command("chmod +x /tests/test.sh", user="root")
            output, _ = await self.execute_command("bash /tests/test.sh", timeout=600, user="root")

            # Read reward
            try:
                content = await self.sandbox.files.read("/logs/verifier/reward.txt")
                reward = float(content.strip() if isinstance(content, str) else content.decode().strip())
                logger.info(f"Test reward: {reward}")
            except Exception as e:
                error_msg = f"Failed to read reward: {e}"

        except Exception as e:
            logger.error(f"Test error: {e}")
            error_msg = str(e)

        # Always save verifier results
        self._save_verifier_result(output, reward, error=error_msg)
        return reward

    def _save_verifier_result(self, output: str, reward: float, error: Optional[str] = None) -> None:
        """Save verifier results to log files."""
        try:
            self.verifier_logs_dir.mkdir(parents=True, exist_ok=True)

            test_log = self.verifier_logs_dir / "test_output.txt"
            with test_log.open("w", encoding="utf-8") as f:
                if error:
                    f.write(f"ERROR: {error}\n")
                    f.write("=" * 80 + "\n")
                if output:
                    f.write(output)

            reward_file = self.verifier_logs_dir / "reward.txt"
            with reward_file.open("w", encoding="utf-8") as f:
                f.write(f"{reward}\n")

            logger.info(f"Verifier results saved to {self.verifier_logs_dir}")
        except Exception as e:
            logger.error(f"Failed to save verifier results: {e}")

    async def cleanup(self) -> None:
        """Clean up the sandbox."""
        if not self.sandbox_id or self.sandbox_id not in _active_sandboxes:
            self.sandbox = self.sandbox_id = None
            return

        try:
            logger.info(f"Closing sandbox {self.sandbox_id}")
            if self.sandbox:
                await asyncio.wait_for(self.sandbox.kill(), timeout=15)
            logger.info(f"Sandbox {self.sandbox_id} closed")
        except Exception as e:
            if "404" not in str(e).lower():
                logger.warning(f"Cleanup error: {e}")
        finally:
            _active_sandboxes.discard(self.sandbox_id)
            self.sandbox = self.sandbox_id = None

    def get_container_id(self) -> Optional[str]:
        return self.sandbox_id
