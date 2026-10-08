# POrchestra: Proactive Agent Orchestration

POrchestra lets an executing SubAgent request changes to its task or resources.
The MainAgent reviews a State–Action–Evidence (SAE) handoff and can revise the
active session while preserving its progress.

## Core idea

- `delegate_task` starts a new SubAgent with instructions, context, tools and a model.
- SubAgents return `finish`, `revise` or `stop` with state and supporting evidence.
- `revise_task` updates task scope, context, tools or step budget and resumes execution.
- MainAgent working memory stores compact handoffs; execution traces remain separate.

## Repository layout

```text
bench_porchestra_gaia.py
bench_porchestra_swebench.py
porchestra/                 # Proactive orchestration and SAE protocol
aorchestra/                # Shared orchestration utilities
base/                      # Agent, model and memory infrastructure
benchmark/                 # Environment adapters; datasets are downloaded separately
config/example/            # Portable configuration templates
```

## Quick start

Run commands from the repository root. Python 3.13 matches the upstream
AOrchestra installation instructions. The dependency set is a starting point
from upstream and still requires clean-environment validation for POrchestra.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/example/model_config.yaml config/model_config.yaml
mkdir -p config/benchmarks
cp config/example/benchmarks/*.yaml config/benchmarks/
```

Set API keys in `.env` and choose available models in `config/model_config.yaml`.
The examples use an OpenAI-compatible endpoint. GAIA web tools also use
`SERPER_API_KEY` and `JINA_API_KEY`. Multimodal tasks may require compatible
vision/audio models and extra document-processing libraries.

## Dataset setup and execution

GAIA requires access to https://huggingface.co/datasets/gaia-benchmark/GAIA.
Download it separately into `benchmark/gaia/data/Gaia/`; the example expects
`2023/validation/metadata.jsonl` and its attachments under that directory.

```bash
python bench_porchestra_gaia.py --config config/benchmarks/porchestra_gaia.yaml
```

SWE-bench requires a running Docker daemon and the official harness:

```bash
pip install -r requirements-swebench.txt
python bench_porchestra_swebench.py --config config/benchmarks/porchestra_swebench.yaml
```

Both examples select one task with concurrency one. Increase limits explicitly
for larger runs. These commands make model API calls. Results go to `workspace/`.
Use `--tasks` to select IDs and `--max_concurrency` to control concurrency.

## Attribution and release status

This is a release draft organized after
[FoundationAgents/AOrchestra](https://github.com/FoundationAgents/AOrchestra).
See `THIRD_PARTY.md` for the reference revision, its license and local changes.
GAIA2, training, checkpoints and experiment datasets are outside this draft's
documented installation scope.

The original POrchestra code's license has not yet been selected. This draft is
not a completed open-source release; complete `RELEASE_CHECKLIST.md` before
publishing. No experiment results or reproduction claims are implied by these
example configurations.
