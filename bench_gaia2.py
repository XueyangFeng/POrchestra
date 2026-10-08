"""Run GAIA2 through ARE from a POrchestra config."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(path=None, *args, **kwargs):
        if path is None:
            path = Path.cwd() / ".env"
        path = Path(path)
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return True


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT.parent / "AOrchestra" / ".env")

from benchmark.gaia2 import GAIA2RunnerConfig, run_gaia2_config


DEFAULT_CONFIG_PATH = ROOT / "config/benchmarks/gaia2.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GAIA2 via ARE are-benchmark.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to GAIA2 YAML config.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve command without running ARE.")
    parser.add_argument("--limit", type=int, default=None, help="Override scenario limit.")
    parser.add_argument("--concurrency", "--max_concurrency", type=int, default=None, help="Override concurrency.")
    parser.add_argument("--timeout", "--scenario_timeout", type=int, default=None, help="Override scenario timeout.")
    parser.add_argument("--max_iterations", "--total_steps", type=int, default=None, help="Override ARE max iterations.")
    parser.add_argument("--subagent_max_steps", type=int, default=None, help="Override orchestrated SubAgent default steps.")
    parser.add_argument("--max_attempts", type=int, default=None, help="Override AOrchestra MainAgent attempt budget.")
    parser.add_argument("--max_batch_size", type=int, default=None, help="Override Orchestra-o1 tasks per batch.")
    parser.add_argument("--output_dir", type=str, default=None, help="Override output root folder.")
    parser.add_argument("--trace_dump_format", type=str, default=None, choices=["lite", "hf", "both"])
    parser.add_argument("--dataset", type=str, default=None, help="Override dataset path.")
    parser.add_argument("--dataset_config", "--are_config", type=str, default=None, help="Override ARE dataset config.")
    parser.add_argument("--split", type=str, default=None, help="Override ARE dataset split.")
    parser.add_argument("--timestamp", type=str, default=None, help="Override output timestamp suffix.")
    parser.add_argument("--shards", "--shard_count", type=int, default=None, help="Total number of dataset shards.")
    parser.add_argument("--shard_index", type=int, default=None, help="Shard index to run, zero-based.")
    parser.add_argument(
        "--use_cli_judge_prompts",
        action="store_true",
        help="Use gaia2-cli soft-checker prompt templates inside ARE validation.",
    )
    args = parser.parse_args()

    cfg = GAIA2RunnerConfig.load(args.config)
    if args.limit is not None:
        cfg.limit = args.limit
    if args.concurrency is not None:
        cfg.max_concurrent_scenarios = args.concurrency
    if args.timeout is not None:
        cfg.scenario_timeout = args.timeout
    if args.max_iterations is not None:
        cfg.max_iterations = args.max_iterations
    if args.subagent_max_steps is not None:
        cfg.subagent_max_steps = args.subagent_max_steps
    if args.max_attempts is not None:
        cfg.max_attempts = args.max_attempts
    if args.max_batch_size is not None:
        cfg.max_batch_size = args.max_batch_size
    if args.output_dir:
        cfg.result_folder = Path(args.output_dir)
    if args.trace_dump_format:
        cfg.trace_dump_format = args.trace_dump_format
    if args.dataset:
        cfg.dataset = Path(args.dataset)
    if args.dataset_config is not None:
        cfg.dataset_config = args.dataset_config
    if args.split is not None:
        cfg.split = args.split
    if args.timestamp is not None:
        cfg.timestamp = args.timestamp
    if args.shards is not None:
        cfg.shard_count = args.shards
    if args.shard_index is not None:
        cfg.shard_index = args.shard_index
    if args.use_cli_judge_prompts:
        cfg.use_cli_judge_prompts = True

    proxy_env = {
        key: value
        for key, value in {
            "OPENAI_PROXY": os.getenv("OPENAI_PROXY"),
            "HTTP_PROXY": os.getenv("HTTP_PROXY"),
            "HTTPS_PROXY": os.getenv("HTTPS_PROXY"),
            "ALL_PROXY": os.getenv("ALL_PROXY"),
            "http_proxy": os.getenv("http_proxy"),
            "https_proxy": os.getenv("https_proxy"),
            "all_proxy": os.getenv("all_proxy"),
            "NO_PROXY": os.getenv("NO_PROXY"),
            "no_proxy": os.getenv("no_proxy"),
        }.items()
        if value
    }

    summary = run_gaia2_config(cfg, dry_run=args.dry_run, extra_env=proxy_env)
    print(f"returncode: {summary['returncode']}")
    print(f"output_dir: {summary['output_dir']}")
    print(f"command_path: {summary['command_path']}")
    if summary.get("log_path"):
        print(f"log_path: {summary['log_path']}")
    if args.dry_run:
        print("command:")
        print(" ".join(summary["command"]))
    if summary["total"]:
        print(
            "accuracy: "
            f"{summary['success']}/{summary['total']} = {summary['accuracy'] * 100:.2f}%"
        )
        print(
            "diagnostics: "
            f"judge_exceptions={summary['judge_exceptions']}, "
            f"max_iterations={summary['max_iterations']}, "
            f"parse_errors={summary['parse_errors']}"
        )
        for name, item in sorted(summary["by_config"].items()):
            total = item["total"]
            success = item["success"]
            print(f"{name}: {success}/{total} = {success / total * 100:.2f}%")
    else:
        print("results: no ARE lite traces yet")
    return int(summary["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
