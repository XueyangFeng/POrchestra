"""Register the release's POrchestra and AOrchestra integrations inside ARE."""


def _run_hook(import_path, function_name):
    try:
        module = __import__(import_path, fromlist=[function_name])
        getattr(module, function_name)()
    except Exception:
        # ARE is optional; unrelated Python commands must still start without it.
        pass


_run_hook("porchestra.judge_marker_parser", "patch_judge_marker_parser")
_run_hook("porchestra.gaia2_agent", "patch_are_builders")
_run_hook("aorchestra.gaia2_agent", "patch_are_builders")
_run_hook("porchestra.gaia2_agent.cli_judge_prompts", "patch_cli_judge_prompts")
_run_hook("porchestra.gaia2_agent.judge_trace", "patch_judge_tracing")
_run_hook("porchestra.gaia2_context_overflow", "patch_context_overflow_failure")
_run_hook("porchestra.gaia2_react_system_ablation", "patch_react_system_info_ablation")
