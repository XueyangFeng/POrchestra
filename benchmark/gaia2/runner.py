"""GAIA2 adapter for the ARE benchmark runner.

POrchestra owns configuration, output placement, and lightweight result
summaries. Scenario execution and validation stay inside ARE via
``are-benchmark``.
"""

from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GAIA2_ROOT = Path("/data0/fengxueyang/gaia2")
DEFAULT_ARE_ROOT = DEFAULT_GAIA2_ROOT / "meta-agents-research-environments"
DEFAULT_ARE_BENCHMARK = DEFAULT_GAIA2_ROOT / ".conda/bin/are-benchmark"
DEFAULT_DATASET = DEFAULT_GAIA2_ROOT / "datasets/gaia2-mini"
DEFAULT_RUNTIME_ROOT = PROJECT_ROOT / "workspace/runtime"
COMPLETION_IDLE_TIMEOUT_SECONDS = 120


@dataclass
class GAIA2RunnerConfig:
    """Config for running GAIA2 through ARE's ``are-benchmark`` CLI."""

    are_root: Path = DEFAULT_ARE_ROOT
    are_benchmark_bin: Path = DEFAULT_ARE_BENCHMARK
    dataset: Path = DEFAULT_DATASET
    dataset_config: str | None = "mini"
    split: str | None = None
    limit: int | None = None
    shard_count: int = 1
    shard_index: int | None = None

    agent: str = "default"
    provider: str = "llama-api"
    model: str = "deepseek-v3.2"
    endpoint: str = "https://api.chatanywhere.tech/v1"
    sub_provider: str | None = None
    sub_model: str | None = None
    sub_endpoint: str | None = None
    reasoning_effort: str | None = None

    judge_provider: str = "llama-api"
    judge_model: str = "deepseek-v3.2"
    judge_endpoint: str = "https://api.chatanywhere.tech/v1"

    max_concurrent_scenarios: int = 50
    executor_type: str = "thread"
    num_runs: int = 1
    max_iterations: int = 300
    subagent_max_steps: int = 30
    max_attempts: int = 10
    max_batch_size: int = 8
    max_planning_rounds: int = 3
    max_roles: int = 8
    max_plan_steps: int = 12
    dependency_output_chars: int = 12000
    skill_path: Path = Path("/data0/fengxueyang/Skill_MAS/init_skill/SKILL.md")
    max_generation_attempts: int = 3
    max_execution_attempts: int = 2
    max_rectification_attempts: int = 2
    workflow_timeout: int = 3600
    mas2_operator_pool: str = "mixed"
    scenario_timeout: int = 1860
    simulated_generation_time_mode: str | None = None
    trace_dump_format: str = "lite"
    log_level: str = "INFO"
    enable_caching: bool = False
    use_cli_judge_prompts: bool = False
    fail_on_context_overflow: bool = True
    react_ablate_system_info: bool = False
    delegation_mask_plan: Path | None = None
    delegation_mask_arm: str = "mask"
    poll_period: int = 0
    aorchestra_error_trigger: bool = False

    api_key_env: str = "OPENAI_COMPAT_API_KEY"
    proxy: str | None = None

    runtime_root: Path = DEFAULT_RUNTIME_ROOT
    result_folder: Path = PROJECT_ROOT / "workspace/logs/gaia2"
    run_name: str = "gaia2_are_react"
    timestamp: str | None = None

    @classmethod
    def load(cls, path: str | Path) -> GAIA2RunnerConfig:
        config_path = Path(path).resolve()
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        cfg = cls()

        cfg.are_root = _resolve_path(raw.get("are_root", cfg.are_root), config_path)
        cfg.are_benchmark_bin = _resolve_path(
            raw.get("are_benchmark_bin", cfg.are_benchmark_bin), config_path
        )
        cfg.dataset = _resolve_path(raw.get("dataset", cfg.dataset), config_path)
        cfg.dataset_config = _optional_str(raw.get("dataset_config", raw.get("config", cfg.dataset_config)))
        cfg.split = _optional_str(raw.get("split", cfg.split))
        cfg.limit = _optional_int(raw.get("limit", cfg.limit))
        cfg.shard_count = int(raw.get("shard_count", raw.get("shards", cfg.shard_count)))
        cfg.shard_index = _optional_int(raw.get("shard_index", cfg.shard_index))

        cfg.agent = str(raw.get("agent", cfg.agent))
        cfg.provider = str(raw.get("provider", raw.get("model_provider", cfg.provider)))
        cfg.model = str(raw.get("model", raw.get("main_model", cfg.model)))
        cfg.endpoint = str(raw.get("endpoint", raw.get("base_url", cfg.endpoint)))
        cfg.sub_provider = _optional_str(raw.get("sub_provider", cfg.sub_provider))
        cfg.sub_model = _optional_str(raw.get("sub_model", cfg.sub_model))
        cfg.sub_endpoint = _optional_str(raw.get("sub_endpoint", raw.get("sub_base_url", cfg.sub_endpoint)))
        cfg.reasoning_effort = _optional_str(
            raw.get("reasoning_effort", cfg.reasoning_effort)
        )
        if cfg.reasoning_effort not in {None, "minimal", "low", "medium", "high"}:
            raise ValueError(
                "reasoning_effort must be one of minimal, low, medium, high"
            )

        cfg.judge_provider = str(raw.get("judge_provider", cfg.judge_provider))
        cfg.judge_model = str(raw.get("judge_model", cfg.judge_model))
        cfg.judge_endpoint = str(raw.get("judge_endpoint", raw.get("judge_base_url", cfg.judge_endpoint)))

        cfg.max_concurrent_scenarios = int(
            raw.get(
                "max_concurrent_scenarios",
                raw.get("concurrency", raw.get("max_concurrency", cfg.max_concurrent_scenarios)),
            )
        )
        cfg.executor_type = str(raw.get("executor_type", cfg.executor_type))
        cfg.num_runs = int(raw.get("num_runs", cfg.num_runs))
        cfg.max_iterations = int(raw.get("max_iterations", raw.get("total_steps", cfg.max_iterations)))
        cfg.subagent_max_steps = int(
            raw.get(
                "subagent_max_steps",
                raw.get("default_subagent_steps", cfg.subagent_max_steps),
            )
        )
        cfg.max_attempts = int(raw.get("max_attempts", cfg.max_attempts))
        cfg.max_batch_size = int(raw.get("max_batch_size", cfg.max_batch_size))
        cfg.max_planning_rounds = int(
            raw.get("max_planning_rounds", cfg.max_planning_rounds)
        )
        cfg.max_roles = int(raw.get("max_roles", cfg.max_roles))
        cfg.max_plan_steps = int(raw.get("max_plan_steps", cfg.max_plan_steps))
        cfg.dependency_output_chars = int(
            raw.get("dependency_output_chars", cfg.dependency_output_chars)
        )
        cfg.skill_path = _resolve_path(raw.get("skill_path", cfg.skill_path), config_path)
        cfg.max_generation_attempts = int(
            raw.get("max_generation_attempts", cfg.max_generation_attempts)
        )
        cfg.max_execution_attempts = int(
            raw.get("max_execution_attempts", cfg.max_execution_attempts)
        )
        cfg.max_rectification_attempts = int(
            raw.get("max_rectification_attempts", cfg.max_rectification_attempts)
        )
        cfg.workflow_timeout = int(raw.get("workflow_timeout", cfg.workflow_timeout))
        cfg.mas2_operator_pool = str(
            raw.get("mas2_operator_pool", cfg.mas2_operator_pool)
        )
        if cfg.mas2_operator_pool not in {"main_only", "sub_only", "mixed"}:
            raise ValueError(
                "mas2_operator_pool must be one of main_only, sub_only, mixed"
            )
        cfg.scenario_timeout = int(raw.get("scenario_timeout", raw.get("timeout", cfg.scenario_timeout)))
        cfg.simulated_generation_time_mode = _optional_str(
            raw.get("simulated_generation_time_mode", cfg.simulated_generation_time_mode)
        )
        cfg.trace_dump_format = str(raw.get("trace_dump_format", cfg.trace_dump_format))
        cfg.log_level = str(raw.get("log_level", cfg.log_level))
        cfg.enable_caching = bool(raw.get("enable_caching", cfg.enable_caching))
        cfg.use_cli_judge_prompts = bool(raw.get("use_cli_judge_prompts", cfg.use_cli_judge_prompts))
        cfg.fail_on_context_overflow = bool(
            raw.get("fail_on_context_overflow", cfg.fail_on_context_overflow)
        )
        cfg.react_ablate_system_info = bool(
            raw.get("react_ablate_system_info", cfg.react_ablate_system_info)
        )

        cfg.api_key_env = str(raw.get("api_key_env", cfg.api_key_env))
        cfg.poll_period = raw.get('poll_period', 0)
        if type(cfg.poll_period) is not int or cfg.poll_period < 0:
            raise ValueError('poll_period must be a nonnegative integer')
        if cfg.poll_period and (cfg.agent not in ('porchestra','aorchestra') or raw.get('delegation_mask_plan')):
            raise ValueError('End-to-end polling requires porchestra without a delegation mask plan')
        cfg.aorchestra_error_trigger = raw.get('aorchestra_error_trigger', False)
        if type(cfg.aorchestra_error_trigger) is not bool:
            raise ValueError('aorchestra_error_trigger must be a boolean')
        if cfg.aorchestra_error_trigger and (cfg.agent != 'aorchestra' or cfg.poll_period or raw.get('delegation_mask_plan')):
            raise ValueError('AOrchestra error trigger requires aorchestra without polling or a delegation mask')
        if raw.get("delegation_mask_plan"):
            cfg.delegation_mask_plan = _resolve_path(raw['delegation_mask_plan'], config_path)
        cfg.delegation_mask_arm = str(raw.get('delegation_mask_arm', 'mask'))
        if cfg.delegation_mask_arm not in {'mask','control'}:
            raise ValueError('delegation_mask_arm must be mask or control')
        if cfg.delegation_mask_plan:
            if cfg.agent != 'porchestra':
                raise ValueError('Delegation masking is only supported for porchestra')
            from porchestra.gaia2_agent.delegation_mask import load_plan
            load_plan(cfg.delegation_mask_plan)
        cfg.proxy = _optional_str(raw.get("proxy", cfg.proxy))

        cfg.runtime_root = _resolve_path(raw.get("runtime_root", cfg.runtime_root), config_path)
        cfg.result_folder = _resolve_path(raw.get("result_folder", cfg.result_folder), config_path)
        cfg.run_name = str(raw.get("run_name", cfg.run_name))
        cfg.timestamp = _optional_str(raw.get("timestamp", cfg.timestamp))
        return cfg

    @property
    def output_dir(self) -> Path:
        stamp = self.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.result_folder / f"{self.run_name}_{stamp}"


def run_gaia2_config(
    cfg: GAIA2RunnerConfig,
    *,
    dry_run: bool = False,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run ARE GAIA2 and return a result summary."""

    output_dir = cfg.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = _with_prepared_shard_dataset(cfg, output_dir)

    command = build_command(cfg, output_dir)
    command_path = output_dir / "are_command.json"
    command_path.write_text(json.dumps(command, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if dry_run:
        summary = summarize_results(output_dir)
        summary.update(
            {
                "returncode": 0,
                "command": command,
                "command_path": str(command_path),
                "output_dir": str(output_dir),
                "log_path": None,
                "dry_run": True,
            }
        )
        return summary

    env = _build_env(cfg, extra_env or {}, output_dir=output_dir)
    env.setdefault(
        "PORCHESTRA_GAIA2_JUDGE_TRACE_DIR",
        str((output_dir / "judge_traces").resolve()),
    )
    env.setdefault(
        "ARE_RAW_LLM_TRACE_DIR",
        str((output_dir / "raw_llm_traces").resolve()),
    )
    env.setdefault(
        "PORCHESTRA_GAIA2_LLM_TRACE_DIR",
        str((output_dir / "llm_calls").resolve()),
    )
    _write_llm_trace_manifest(Path(env["PORCHESTRA_GAIA2_LLM_TRACE_DIR"]))
    env.setdefault(
        "PORCHESTRA_GAIA2_BOUNDARY_TRACE_DIR",
        str((output_dir / "boundary_traces").resolve()),
    )
    log_path = output_dir / "runner.log"
    with log_path.open("w", encoding="utf-8") as log_file:
        returncode = _run_are_command(command, cfg, env, log_file)

    summary = summarize_results(output_dir)
    summary.update(
        {
            "returncode": returncode,
            "command": command,
            "command_path": str(command_path),
            "output_dir": str(output_dir),
            "log_path": str(log_path),
            "dry_run": False,
        }
    )
    return summary


def _write_llm_trace_manifest(trace_dir: Path) -> None:
    """Document the lossless per-scenario JSONL format used for training data."""

    trace_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "format": "jsonl",
        "partitioning": "one file per scenario_id",
        "roles": ["main_agent", "subagent", "judge"],
        "ordering": "sequence is strictly increasing within each scenario file",
        "records": {
            "llm_call": {
                "request": (
                    "complete ARE messages, actual provider_messages, stop sequences, "
                    "and non-secret kwargs"
                ),
                "response": "complete model text and metadata/usage",
                "failure": "error type/message with response set to null",
            },
            "judge_llm_function": "complete judge messages, response, retries, and checker",
            "judge_llm_checker": "judge vote aggregation and parsed result",
        },
        "related_artifacts": {
            "scenario_trace": "../scenario_<id>_<run>.json",
            "boundary_trace": "../boundary_traces/<scenario_id>.jsonl",
            "judge_trace": "../judge_traces/judge_llm_calls.jsonl",
            "raw_provider_trace": "../raw_llm_traces/openai_compat_raw.jsonl",
        },
        "credential_policy": (
            "Authorization headers and credential-like structured fields are not stored. "
            "Model-visible message content is preserved exactly."
        ),
    }
    (trace_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_are_command(
    command: list[str],
    cfg: GAIA2RunnerConfig,
    env: dict[str, str],
    log_file,
) -> int:
    """Run ARE while guarding against post-completion cleanup hangs."""

    proc = subprocess.Popen(
        command,
        # Several agent integrations initialize relative log files at import
        # time.  Keep their working directory in the writable project tree;
        # ``cfg.are_root`` is already present in PYTHONPATH for ARE imports.
        cwd=str(PROJECT_ROOT.resolve()),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        start_new_session=True,
    )
    assert proc.stdout is not None

    completion_seen = False
    last_output_at = time.monotonic()
    completion_idle_timeout = int(
        env.get("PORCHESTRA_GAIA2_COMPLETION_IDLE_TIMEOUT", COMPLETION_IDLE_TIMEOUT_SECONDS)
    )

    try:
        while True:
            ready, _, _ = select.select([proc.stdout], [], [], 1.0)
            if ready:
                line = proc.stdout.readline()
                if line == "":
                    if proc.poll() is not None:
                        break
                    continue
                _write_process_line(line, log_file)
                last_output_at = time.monotonic()
                if _is_scenario_completion_line(line):
                    completion_seen = True
                continue

            returncode = proc.poll()
            if returncode is not None:
                _drain_process_stdout(proc, log_file)
                return returncode

            if completion_seen and time.monotonic() - last_output_at >= completion_idle_timeout:
                message = (
                    "\n[POrchestra GAIA2] ARE appears complete but did not exit after "
                    f"{completion_idle_timeout}s of silence; terminating process group.\n"
                )
                _write_process_line(message, log_file)
                _terminate_process_group(proc)
                return 0
    except KeyboardInterrupt:
        _write_process_line(
            "\n[POrchestra GAIA2] Parent interrupted; terminating ARE process group.\n",
            log_file,
        )
        _terminate_process_group(proc)
        return 130
    except BaseException:
        _terminate_process_group(proc)
        raise

    return proc.wait()


def _write_process_line(line: str, log_file) -> None:
    print(line, end="", flush=True)
    log_file.write(line)
    log_file.flush()


def _drain_process_stdout(proc: subprocess.Popen, log_file) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        _write_process_line(line, log_file)


def _terminate_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        proc.wait(timeout=10)


def _is_scenario_completion_line(line: str) -> bool:
    text = _strip_ansi(line).replace("\r", "")
    return bool(re.search(r"Running .*scenarios:\s+100%", text))


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def build_command(cfg: GAIA2RunnerConfig, output_dir: Path) -> list[str]:
    """Build the ``are-benchmark`` command without invoking a shell."""

    command = [
        str(cfg.are_benchmark_bin.resolve()),
        "--log-level",
        cfg.log_level,
        "--agent",
        cfg.agent,
        "--provider",
        cfg.provider,
        "--model",
        cfg.model,
        "--endpoint",
        cfg.endpoint,
        "--dataset",
        str(cfg.dataset.resolve()),
        "--max_concurrent_scenarios",
        str(cfg.max_concurrent_scenarios),
        "--executor_type",
        cfg.executor_type,
        "--num_runs",
        str(cfg.num_runs),
        "--scenario_timeout",
        str(cfg.scenario_timeout),
        "--judge_provider",
        cfg.judge_provider,
        "--judge_model",
        cfg.judge_model,
        "--judge_endpoint",
        cfg.judge_endpoint,
        "--output_dir",
        str(output_dir),
        "--trace_dump_format",
        cfg.trace_dump_format,
    ]
    if cfg.dataset_config:
        command.extend(["--config", cfg.dataset_config])
    if cfg.split:
        command.extend(["--split", cfg.split])
    if cfg.limit is not None:
        command.extend(["--limit", str(cfg.limit)])
    if cfg.simulated_generation_time_mode:
        command.extend(["--simulated_generation_time_mode", cfg.simulated_generation_time_mode])
    if cfg.enable_caching:
        command.append("--enable_caching")
    command.append("run")
    return command


def _with_prepared_shard_dataset(cfg: GAIA2RunnerConfig, output_dir: Path) -> GAIA2RunnerConfig:
    """Create a small local dataset view when a shard is requested."""

    if cfg.shard_count <= 1:
        return cfg
    if cfg.shard_index is None:
        raise ValueError("shard_index must be set when shard_count > 1")
    if not 0 <= cfg.shard_index < cfg.shard_count:
        raise ValueError(f"shard_index must be in [0, {cfg.shard_count}); got {cfg.shard_index}")

    source_dir = cfg.dataset
    if cfg.dataset_config:
        source_dir = source_dir / cfg.dataset_config
    if cfg.split:
        source_dir = source_dir / cfg.split
    scenario_paths = sorted(source_dir.glob("*.json"))
    if not scenario_paths:
        raise FileNotFoundError(f"No GAIA2 scenario JSON files found in {source_dir}")

    selected = [
        path
        for index, path in enumerate(scenario_paths)
        if index % cfg.shard_count == cfg.shard_index
    ]
    shard_root = output_dir / "_dataset_shard"
    shard_dir = shard_root
    if cfg.dataset_config:
        shard_dir = shard_dir / cfg.dataset_config
    if cfg.split:
        shard_dir = shard_dir / cfg.split
    shard_dir.mkdir(parents=True, exist_ok=True)

    for path in selected:
        target = shard_dir / path.name
        if not target.exists():
            target.symlink_to(path)

    manifest = {
        "source_dir": str(source_dir),
        "dataset": str(cfg.dataset),
        "dataset_config": cfg.dataset_config,
        "split": cfg.split,
        "shard_count": cfg.shard_count,
        "shard_index": cfg.shard_index,
        "total_scenarios": len(scenario_paths),
        "selected_scenarios": len(selected),
        "scenario_ids": [path.stem for path in selected],
    }
    (output_dir / "shard_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    cfg = replace(cfg)
    cfg.dataset = shard_root
    cfg.limit = None
    return cfg


def summarize_results(output_dir: str | Path) -> dict[str, Any]:
    """Summarize ARE lite traces dumped by ``are-benchmark``."""

    output_dir = Path(output_dir)
    rows = _load_lite_rows(output_dir)
    total = len(rows)
    success = 0
    invalid = 0
    errors = 0
    judge_exceptions = 0
    max_iterations = 0
    parse_errors = 0
    by_config: dict[str, dict[str, int]] = {}

    for row in rows:
        decision = row.get("validation_decision")
        rationale = str(row.get("validation_rationale") or "")
        if decision == "Valid":
            success += 1
        elif decision == "Invalid":
            invalid += 1
        else:
            errors += 1
        if rationale == "Exception" or "Unmapped LLM provider" in rationale:
            judge_exceptions += 1
        events = row.get("events") or []
        text_blob = json.dumps(events, ensure_ascii=False)
        if "Max iterations reached" in text_blob:
            max_iterations += 1
        if "Could not parse the given action" in text_blob or "No 'Action:' token" in text_blob:
            parse_errors += 1
        config_name = str(row.get("dataset_config") or _infer_config_from_path(row) or "unknown")
        item = by_config.setdefault(config_name, {"total": 0, "success": 0, "invalid": 0, "errors": 0})
        item["total"] += 1
        if decision == "Valid":
            item["success"] += 1
        elif decision == "Invalid":
            item["invalid"] += 1
        else:
            item["errors"] += 1

    return {
        "results_path": str(output_dir / "lite"),
        "total": total,
        "success": success,
        "invalid": invalid,
        "errors": errors,
        "accuracy": (success / total) if total else None,
        "judge_exceptions": judge_exceptions,
        "max_iterations": max_iterations,
        "parse_errors": parse_errors,
        "by_config": by_config,
    }


def _load_lite_rows(output_dir: Path) -> list[dict[str, Any]]:
    lite_dir = output_dir / "lite"
    paths = sorted(lite_dir.glob("*.json")) if lite_dir.exists() else []
    if not paths:
        paths = sorted(output_dir.glob("scenario_*.json"))
    rows: list[dict[str, Any]] = []
    for path in paths:
        try:
            row = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            row.setdefault("_path", str(path))
            rows.append(row)
    return rows


def _build_env(
    cfg: GAIA2RunnerConfig,
    extra_env: dict[str, str],
    *,
    output_dir: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(extra_env)

    runtime_root = cfg.runtime_root.resolve()
    runtime_paths = {
        "TMPDIR": runtime_root / "tmp",
        "RAY_TMPDIR": runtime_root / "ray",
        "XDG_CACHE_HOME": runtime_root / "cache",
        "HF_HOME": runtime_root / "cache/huggingface",
        "TORCH_HOME": runtime_root / "cache/torch",
        "PIP_CACHE_DIR": runtime_root / "cache/pip",
        "POETRY_CACHE_DIR": runtime_root / "cache/pypoetry",
        "TORCHINDUCTOR_CACHE_DIR": runtime_root / "cache/torchinductor",
    }
    for name, path in runtime_paths.items():
        path.mkdir(parents=True, exist_ok=True)
        if name not in extra_env:
            env[name] = str(path)
    if "TEMP" not in extra_env:
        env["TEMP"] = env["TMPDIR"]
    if "TMP" not in extra_env:
        env["TMP"] = env["TMPDIR"]

    pythonpath = os.pathsep.join([str(PROJECT_ROOT.resolve()), str(cfg.are_root.resolve())])
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath

    key = (
        env.get(cfg.api_key_env)
        or env.get("OPENAI_COMPAT_API_KEY")
        or env.get("CHATANYWHERE_API_KEY")
        or env.get("DEEPSEEK_API_KEY")
        or env.get("OPENAI_API_KEY")
    )
    if key:
        env.setdefault(cfg.api_key_env, key)
        env.setdefault("OPENAI_COMPAT_API_KEY", key)
        env.setdefault("OPENAI_API_KEY", key)
        env.setdefault("LLAMA_API_KEY", key)

    # Clear inherited experiment controls unless explicitly configured for this run.
    for key in ('PORCHESTRA_DELEGATION_MASK_PLAN', 'PORCHESTRA_DELEGATION_MASK_ARM',
                'PORCHESTRA_DELEGATION_MASK_TRACE_DIR'):
        env.pop(key, None)
    if cfg.delegation_mask_plan:
        env['PORCHESTRA_DELEGATION_MASK_PLAN'] = str(cfg.delegation_mask_plan.resolve())
        env['PORCHESTRA_DELEGATION_MASK_ARM'] = cfg.delegation_mask_arm
        env['PORCHESTRA_DELEGATION_MASK_TRACE_DIR'] = str(output_dir / 'delegation_masks')

    env['PORCHESTRA_GAIA2_POLL_PERIOD'] = str(cfg.poll_period if cfg.agent=='porchestra' else 0)
    env['AORCHESTRA_GAIA2_POLL_PERIOD'] = str(cfg.poll_period if cfg.agent=='aorchestra' else 0)
    env['AORCHESTRA_GAIA2_ERROR_TRIGGER'] = '1' if cfg.aorchestra_error_trigger else '0'
    if cfg.endpoint:
        env.setdefault("OPENAI_BASE_URL", cfg.endpoint)
        env.setdefault("LLAMA_API_BASE", cfg.endpoint)

    if cfg.sub_model:
        env["PORCHESTRA_SUB_MODEL"] = cfg.sub_model
        env["PORCHESTRA_SUB_PROVIDER"] = cfg.sub_provider or cfg.provider
        env["PORCHESTRA_SUB_ENDPOINT"] = cfg.sub_endpoint or cfg.endpoint
        env["AORCHESTRA_SUB_MODEL"] = cfg.sub_model
        env["AORCHESTRA_SUB_PROVIDER"] = cfg.sub_provider or cfg.provider
        env["AORCHESTRA_SUB_ENDPOINT"] = cfg.sub_endpoint or cfg.endpoint
        env["ORCHESTRA_O1_SUB_MODEL"] = cfg.sub_model
        env["ORCHESTRA_O1_SUB_PROVIDER"] = cfg.sub_provider or cfg.provider
        env["ORCHESTRA_O1_SUB_ENDPOINT"] = cfg.sub_endpoint or cfg.endpoint
        env["SKILL_MAS_GAIA2_SUB_MODEL"] = cfg.sub_model
        env["SKILL_MAS_GAIA2_SUB_PROVIDER"] = cfg.sub_provider or cfg.provider
        env["SKILL_MAS_GAIA2_SUB_ENDPOINT"] = cfg.sub_endpoint or cfg.endpoint
        env["MAS2_GAIA2_SUB_MODEL"] = cfg.sub_model
        env["MAS2_GAIA2_SUB_PROVIDER"] = cfg.sub_provider or cfg.provider
        env["MAS2_GAIA2_SUB_ENDPOINT"] = cfg.sub_endpoint or cfg.endpoint
        env["AUTOAGENTS_GAIA2_SUB_MODEL"] = cfg.sub_model
        env["AUTOAGENTS_GAIA2_SUB_PROVIDER"] = cfg.sub_provider or cfg.provider
        env["AUTOAGENTS_GAIA2_SUB_ENDPOINT"] = cfg.sub_endpoint or cfg.endpoint

    env["PORCHESTRA_GAIA2_MAX_ITERATIONS"] = str(cfg.max_iterations)
    env["PORCHESTRA_GAIA2_SUBAGENT_STEPS"] = str(cfg.subagent_max_steps)
    env["AORCHESTRA_GAIA2_MAX_ITERATIONS"] = str(cfg.max_iterations)
    env["AORCHESTRA_GAIA2_SUBAGENT_STEPS"] = str(cfg.subagent_max_steps)
    env["AORCHESTRA_GAIA2_MAX_ATTEMPTS"] = str(cfg.max_attempts)
    env["ORCHESTRA_O1_GAIA2_MAX_ITERATIONS"] = str(cfg.max_iterations)
    env["ORCHESTRA_O1_GAIA2_SUBAGENT_STEPS"] = str(cfg.subagent_max_steps)
    env["ORCHESTRA_O1_GAIA2_MAX_ATTEMPTS"] = str(cfg.max_attempts)
    env["ORCHESTRA_O1_GAIA2_MAX_BATCH_SIZE"] = str(cfg.max_batch_size)
    env["SKILL_MAS_GAIA2_MAX_ITERATIONS"] = str(cfg.max_iterations)
    env["SKILL_MAS_GAIA2_SUBAGENT_STEPS"] = str(cfg.subagent_max_steps)
    env["SKILL_MAS_GAIA2_GENERATION_ATTEMPTS"] = str(cfg.max_generation_attempts)
    env["SKILL_MAS_GAIA2_EXECUTION_ATTEMPTS"] = str(cfg.max_execution_attempts)
    env["SKILL_MAS_GAIA2_SKILL_PATH"] = str(cfg.skill_path)
    env["SKILL_MAS_ROOT"] = str(cfg.skill_path.parent.parent)
    env["SKILL_MAS_GAIA2_TRACE_DIR"] = str((output_dir / "skill_mas_traces").resolve())
    env["MAS2_GAIA2_MAX_ITERATIONS"] = str(cfg.max_iterations)
    env["MAS2_GAIA2_SUBAGENT_STEPS"] = str(cfg.subagent_max_steps)
    env["MAS2_GAIA2_GENERATION_ATTEMPTS"] = str(cfg.max_generation_attempts)
    env["MAS2_GAIA2_RECTIFICATION_ATTEMPTS"] = str(cfg.max_rectification_attempts)
    env["MAS2_GAIA2_WORKFLOW_TIMEOUT"] = str(cfg.workflow_timeout)
    env["MAS2_GAIA2_OPERATOR_POOL"] = cfg.mas2_operator_pool
    env["MAS2_GAIA2_TRACE_DIR"] = str((output_dir / "mas2_traces").resolve())
    env["AUTOAGENTS_GAIA2_MAX_ITERATIONS"] = str(cfg.max_iterations)
    env["AUTOAGENTS_GAIA2_SUBAGENT_STEPS"] = str(cfg.subagent_max_steps)
    env["AUTOAGENTS_GAIA2_PLANNING_ROUNDS"] = str(cfg.max_planning_rounds)
    env["AUTOAGENTS_GAIA2_MAX_ROLES"] = str(cfg.max_roles)
    env["AUTOAGENTS_GAIA2_MAX_PLAN_STEPS"] = str(cfg.max_plan_steps)
    env["AUTOAGENTS_GAIA2_DEPENDENCY_OUTPUT_CHARS"] = str(
        cfg.dependency_output_chars
    )
    env["AUTOAGENTS_GAIA2_TRACE_DIR"] = str(
        (output_dir / "autoagents_traces").resolve()
    )
    env["MINI_SWE_GAIA2_MAX_ITERATIONS"] = str(cfg.max_iterations)
    if cfg.reasoning_effort:
        env["MINI_SWE_GAIA2_REASONING_EFFORT"] = cfg.reasoning_effort
        env["AORCHESTRA_GAIA2_SUB_REASONING_EFFORT"] = cfg.reasoning_effort
        env["MAS2_GAIA2_GEMINI_OPERATOR_REASONING_EFFORT"] = (
            cfg.reasoning_effort
        )
        env["ORCHESTRA_O1_GAIA2_SUB_REASONING_EFFORT"] = cfg.reasoning_effort
        env["AUTOAGENTS_GAIA2_SUB_REASONING_EFFORT"] = cfg.reasoning_effort
        env["SKILL_MAS_GAIA2_SUB_REASONING_EFFORT"] = cfg.reasoning_effort

    if cfg.use_cli_judge_prompts:
        env["PORCHESTRA_GAIA2_CLI_JUDGE_PROMPTS"] = "1"
    if cfg.fail_on_context_overflow:
        env["PORCHESTRA_GAIA2_FAIL_ON_CONTEXT_OVERFLOW"] = "1"
    if cfg.react_ablate_system_info:
        env["PORCHESTRA_GAIA2_REACT_ABLATE_SYSTEM_INFO"] = "1"

    if cfg.proxy:
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env[name] = cfg.proxy
        env.setdefault("NO_PROXY", "localhost,127.0.0.1")
        env.setdefault("no_proxy", env["NO_PROXY"])
    return env


def _infer_config_from_path(row: dict[str, Any]) -> str | None:
    path = str(row.get("_path") or row.get("scenario_file") or row.get("scenario_path") or "")
    for name in ("mini", "search", "execution", "time", "ambiguity", "adaptability"):
        if f"/{name}/" in path or path.startswith(f"{name}/"):
            return name
    return None


def _resolve_path(value: str | Path, config_path: Path) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


def _optional_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
