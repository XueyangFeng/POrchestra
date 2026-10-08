"""Result reporter for Terminal Bench."""
from pathlib import Path
from typing import Dict

from benchmark.common.runner import LevelResult


def print_results(
    results: Dict[str, LevelResult],
    csv_path: Path,
    trajectory_folder: Path,
):
    """Calculate and display benchmark results."""
    total_reward = sum(r.total_reward for r in results.values())
    num_tasks = len(results)
    avg_reward = total_reward / num_tasks if num_tasks > 0 else 0.0
    cost = sum(r.cost for r in results.values())

    # Count successful tasks (reward > 0)
    successful_tasks = sum(1 for r in results.values() if r.total_reward > 0)
    success_rate = successful_tasks / num_tasks if num_tasks > 0 else 0.0

    print("\n" + "=" * 70)
    print("Terminal Bench 2.0 Results")
    print("=" * 70)
    print(f"Total Tasks: {num_tasks}")
    print(f"Successful Tasks: {successful_tasks}")
    print(f"Success Rate: {success_rate:.2%}")
    print(f"Total Reward: {total_reward:.4f}")
    print(f"Average Reward: {avg_reward:.4f}")
    print(f"Total Cost: ${cost:.4f}")
    print(f"\nResults saved to: {csv_path}")
    print(f"Trajectories saved to: {trajectory_folder}")
    print("=" * 70)

