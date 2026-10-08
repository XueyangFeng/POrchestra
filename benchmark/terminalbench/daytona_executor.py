"""Daytona executor for Terminal Bench tasks."""
from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple

from daytona import AsyncDaytona, CreateSandboxFromImageParams, DaytonaConfig, FileUpload
from daytona.common.process import ExecuteResponse

from base.engine.logs import logger
from benchmark.terminalbench.base_executor import BaseExecutor


DEFAULT_TIMEOUT = 600
MAX_RETRIES = 3
RETRY_DELAY = 2


class DaytonaExecutor(BaseExecutor):
    """Executes Terminal Bench tasks in Daytona sandboxes."""

    def __init__(
        self,
        task_id: str,
        task_dir: Path,
        task_config: dict,
        verifier_logs_dir: Path,
        agent_logs_dir: Path,
        timeout: int = DEFAULT_TIMEOUT,
        env_init: Optional[dict[str, str]] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        target: Optional[str] = None,
    ):
        super().__init__(
            task_id=task_id,
            task_dir=task_dir,
            task_config=task_config,
            verifier_logs_dir=verifier_logs_dir,
            agent_logs_dir=agent_logs_dir,
            timeout=timeout,
            env_init=env_init,
        )

        config_kwargs = {}
        if api_key:
            config_kwargs["api_key"] = api_key
        if api_url:
            config_kwargs["api_url"] = api_url
        if target:
            config_kwargs["target"] = target

        self.daytona_config = DaytonaConfig(**config_kwargs) if config_kwargs else None
        self.daytona: Optional[AsyncDaytona] = None
        self.sandbox = None
        self.sandbox_id: Optional[str] = None
        
        self.environment_dir = task_dir / "environment"
        self.dockerfile_path = self.environment_dir / "Dockerfile"
        self.workdir = self._extract_workdir()

    def _extract_workdir(self) -> Optional[str]:
        """Extract WORKDIR from Dockerfile."""
        if not self.dockerfile_path.exists():
            return None
        try:
            for line in reversed(self.dockerfile_path.read_text().splitlines()):
                parts = line.strip().split(maxsplit=1)
                if parts and parts[0].upper() == "WORKDIR" and len(parts) == 2:
                    return parts[1]
        except Exception:
            pass
        return None

    def _get_image_name(self) -> str:
        """Get image name from task.toml or generate one."""
        env_config = self.task_config.get("environment", {})
        docker_image = env_config.get("docker_image")
        
        if docker_image:
            return docker_image
        
        session_id = str(uuid.uuid4())[:8]
        return f"tbench-{self.task_id}-{session_id}".lower().replace("_", "-")

    def _build_dockerfile_content(self) -> str:
        """Read Dockerfile and inject environment variables."""
        if not self.dockerfile_path.exists():
            raise FileNotFoundError(f"Dockerfile not found: {self.dockerfile_path}")
        
        content = self.dockerfile_path.read_text()
        
        if self.env_init:
            lines = content.split("\n")
            env_instructions = [f"ENV {k}={v}" for k, v in self.env_init.items() if v]
            
            if env_instructions:
                new_lines = []
                inserted = False
                for line in lines:
                    new_lines.append(line)
                    if not inserted and line.strip().upper().startswith("FROM "):
                        new_lines.extend(env_instructions)
                        inserted = True
                content = "\n".join(new_lines)
        
        return content

    async def _build_image_locally(self, image_name: str) -> None:
        """Build Docker image locally."""
        logger.info(f"Building image {image_name} from Dockerfile")
        
        proc = await asyncio.create_subprocess_exec(
            "docker", "build",
            "-t", image_name,
            "-f", str(self.dockerfile_path),
            str(self.environment_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        stdout, _ = await asyncio.wait_for(
            proc.communicate(),
            timeout=self.timeout,
        )
        
        if proc.returncode != 0:
            output = stdout.decode("utf-8", errors="replace")
            raise RuntimeError(f"Failed to build image: {output}")
        
        logger.info(f"Image {image_name} built successfully")

    async def start_container(self, use_prebuilt_image: bool = True) -> None:
        """Start Daytona sandbox."""
        try:
            if self.daytona_config:
                self.daytona = AsyncDaytona(self.daytona_config)
            else:
                self.daytona = AsyncDaytona()

            image_name = self._get_image_name()
            
            env_config = self.task_config.get("environment", {})
            if not use_prebuilt_image or not env_config.get("docker_image"):
                if self.dockerfile_path.exists():
                    await self._build_image_locally(image_name)
                else:
                    logger.warning(f"No Dockerfile found, using default image")
                    image_name = "python:3.13-slim"

            cpus = env_config.get("cpus", 1)
            memory_str = env_config.get("memory", "2G")
            memory_gib = self._parse_memory_to_gib(memory_str)
            
            from daytona.common.sandbox import Resources
            
            params = CreateSandboxFromImageParams(
                image=image_name,
                env_vars=self.env_init or {},
                auto_stop_interval=60,
                auto_delete_interval=120,
                resources=Resources(
                    cpu=cpus,
                    memory=memory_gib,
                ),
            )
            for attempt in range(MAX_RETRIES):
                try:
                    logger.info(f"Creating Daytona sandbox from image {image_name} (attempt {attempt + 1})")
                    self.sandbox = await asyncio.wait_for(
                        self.daytona.create(params),
                        timeout=120,
                    )
                    self.sandbox_id = self.sandbox.id
                    logger.info(f"Sandbox created: {self.sandbox_id}")
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Failed to create sandbox (attempt {attempt + 1}): {e}")
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        raise

            await self._setup_directories()
            
            logger.info(f"Container ready for task {self.task_id}")

        except Exception as e:
            logger.error(f"Failed to start container for {self.task_id}: {type(e).__name__}: {e}")
            await self.cleanup()
            raise

    def _parse_memory_to_gib(self, memory_str: str) -> int:
        """Parse memory string (e.g. '2G') to GiB."""
        memory_str = str(memory_str).upper().strip()
        
        if memory_str.endswith("G"):
            return int(float(memory_str[:-1]))
        elif memory_str.endswith("M"):
            return max(1, int(float(memory_str[:-1]) / 1024))
        elif memory_str.endswith("K"):
            return 1
        else:
            return max(1, int(int(memory_str) / (1024 * 1024 * 1024)))

    async def _setup_directories(self) -> None:
        """Create required directories in sandbox."""
        try:
            await asyncio.wait_for(
                self.sandbox.process.exec("mkdir -p /logs/agent /logs/verifier", timeout=10),
                timeout=15,
            )
        except Exception as e:
            logger.warning(f"Failed to create directories: {e}")

    async def execute_command(
        self, 
        command: str, 
        timeout: Optional[int] = None
    ) -> Tuple[str, int]:
        """Execute command in sandbox."""
        if not self.sandbox:
            raise RuntimeError("Sandbox not started")

        cmd_timeout = int(timeout or self.timeout)

        try:
            response: ExecuteResponse = await asyncio.wait_for(
                self.sandbox.process.exec(
                    command=command,
                    cwd=self.workdir,
                    timeout=cmd_timeout,
                ),
                timeout=cmd_timeout + 10,
            )
            
            logger.info(f"Command result: exit_code={response.exit_code}")
            return response.result, response.exit_code

        except asyncio.TimeoutError:
            logger.error(f"Command timeout ({cmd_timeout}s): {command[:100]}")
            return f"Command timeout after {cmd_timeout} seconds", 124
        except Exception as e:
            logger.error(f"Command error: {e}")
            return str(e), 1

    async def run_tests(self) -> float:
        """Run tests and return reward."""
        if not self.sandbox:
            raise RuntimeError("Sandbox not started")

        test_script = self.task_dir / "tests" / "test.sh"
        if not test_script.exists():
            logger.error(f"Test script not found: {test_script}")
            return 0.0

        try:
            tests_dir = self.task_dir / "tests"
            files_to_upload = []
            
            for test_file in tests_dir.rglob("*"):
                if test_file.is_file():
                    rel_path = test_file.relative_to(tests_dir)
                    remote_path = f"/tests/{rel_path}"
                    files_to_upload.append(
                        FileUpload(
                            source=str(test_file),
                            destination=remote_path,
                        )
                    )
            
            if files_to_upload:
                await self.sandbox.fs.upload_files(files_to_upload, timeout=120)
                logger.info(f"Uploaded {len(files_to_upload)} test files")

            await self.execute_command("chmod +x /tests/test.sh", timeout=10)

            test_timeout = int(self.task_config.get("verifier", {}).get("timeout_sec", 900))
            output, _ = await self.execute_command(
                "bash /tests/test.sh",
                timeout=test_timeout,
            )

            (self.verifier_logs_dir / "test_output.txt").write_text(
                output, 
                encoding="utf-8", 
                errors="replace",
            )

            try:
                reward_content = await self.sandbox.fs.download_file("/logs/verifier/reward.txt")
                if reward_content:
                    reward_str = reward_content.decode("utf-8").strip()
                    reward = float(reward_str)
                    logger.info(f"Test reward: {reward}")
                    return reward
                else:
                    logger.error("Reward file is empty")
                    return 0.0
            except Exception as e:
                logger.error(f"Failed to read reward: {e}")
                return 0.0

        except Exception as e:
            logger.error(f"Test error: {e}")
            return 0.0

    async def cleanup(self) -> None:
        """Cleanup sandbox."""
        if not self.sandbox_id:
            self.sandbox = None
            self.daytona = None
            return

        try:
            logger.info(f"Deleting sandbox {self.sandbox_id}")
            if self.daytona and self.sandbox:
                await asyncio.wait_for(
                    self.daytona.delete(self.sandbox),
                    timeout=15,
                )
            logger.info(f"Sandbox {self.sandbox_id} deleted")
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        finally:
            self.sandbox = None
            self.sandbox_id = None
            self.daytona = None

    def get_container_id(self) -> Optional[str]:
        return self.sandbox_id

