"""Result reporter for SWE-bench benchmark."""
from pathlib import Path
from typing import Dict

from benchmark.common.runner import LevelResult


def print_results(
    results: Dict[str, LevelResult],
    csv_path: Path,
    trajectory_folder: Path,
):
    """Calculate and display SWE-bench benchmark results."""
    total_reward = sum(r.total_reward for r in results.values())
    num_tasks = len(results)
    avg_reward = total_reward / num_tasks if num_tasks > 0 else 0.0
    cost = sum(r.cost for r in results.values())

    # Count successful tasks (reward > 0, i.e., resolved)
    resolved_tasks = sum(1 for r in results.values() if r.total_reward > 0)
    resolve_rate = resolved_tasks / num_tasks if num_tasks > 0 else 0.0

    # Calculate token usage
    total_input_tokens = sum(r.input_tokens for r in results.values())
    total_output_tokens = sum(r.output_tokens for r in results.values())
    avg_steps = sum(r.steps for r in results.values()) / num_tasks if num_tasks > 0 else 0.0

    print("\n" + "=" * 70)
    print("SWE-bench Verified Results")
    print("=" * 70)
    print(f"Total Instances: {num_tasks}")
    print(f"Resolved: {resolved_tasks}")
    print(f"Resolve Rate: {resolve_rate:.2%}")
    print("-" * 70)
    print(f"Average Steps: {avg_steps:.1f}")
    print(f"Total Input Tokens: {total_input_tokens:,}")
    print(f"Total Output Tokens: {total_output_tokens:,}")
    print(f"Total Cost: ${cost:.4f}")
    print("-" * 70)
    print(f"Results saved to: {csv_path}")
    print(f"Trajectories saved to: {trajectory_folder}")
    print("=" * 70)


def generate_summary_report(
    results: Dict[str, LevelResult],
    output_path: Path,
):
    """Generate a detailed summary report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with output_path.open("w", encoding="utf-8") as f:
        f.write("# SWE-bench Verified Summary Report\n\n")
        
        # Overall statistics
        num_tasks = len(results)
        resolved = sum(1 for r in results.values() if r.total_reward > 0)
        
        f.write("## Overall Statistics\n\n")
        f.write(f"- Total Instances: {num_tasks}\n")
        f.write(f"- Resolved: {resolved}\n")
        f.write(f"- Resolve Rate: {resolved/num_tasks*100:.1f}%\n\n")
        
        # Per-instance results
        f.write("## Per-Instance Results\n\n")
        f.write("| Instance ID | Status | Steps | Cost |\n")
        f.write("|-------------|--------|-------|------|\n")
        
        for instance_id, result in sorted(results.items()):
            status = "✓ Resolved" if result.total_reward > 0 else "✗ Failed"
            f.write(f"| {instance_id} | {status} | {result.steps} | ${result.cost:.4f} |\n")
        
        f.write("\n")
    
    return output_path

