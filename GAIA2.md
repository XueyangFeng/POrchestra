# GAIA2 setup

GAIA2 runs POrchestra inside Meta Agents Research Environments (ARE).
`sitecustomize.py` registers the agents when ARE starts.

## ARE environment

The local experiments use Meta Agents Research Environments (ARE) at revision
`7946367413129784139e785ae4c351090002a0bb`, plus the compatibility changes in
`integrations/are-compat.patch`. These include an OpenAI-compatible LLM engine
and execution/validation changes. The patch's source license is preserved in
`licenses/ARE-MIT.txt`. Install ARE separately from the GAIA/SWE-bench environment:

```bash
mkdir -p workspace
git clone https://github.com/facebookresearch/meta-agents-research-environments.git workspace/are
git -C workspace/are checkout 7946367413129784139e785ae4c351090002a0bb
git -C workspace/are apply ../../integrations/are-compat.patch
python -m venv workspace/are-env
workspace/are-env/bin/pip install -e workspace/are
workspace/are-env/bin/pip install python-dotenv PyYAML
mkdir -p config/benchmarks
cp config/example/benchmarks/porchestra_gaia2.yaml config/benchmarks/
cp .env.example .env
```

Download the GAIA2 dataset from https://huggingface.co/datasets/meta-agents/gaia2
following the upstream ARE instructions. The example
expects a local dataset at `workspace/datasets/gaia2-mini`; set `dataset`,
`dataset_config` and `split` to match your actual dataset layout.

## Run

Set `OPENAI_API_KEY` in `.env`. Adjust the MainAgent (`model`), SubAgent
(`sub_model`) and judge (`judge_model`) with their providers and endpoints.
The example uses `gpt-4o` for all three model roles.

```bash
workspace/are-env/bin/python bench_gaia2.py --config config/benchmarks/porchestra_gaia2.yaml --dry-run
workspace/are-env/bin/python bench_gaia2.py --config config/benchmarks/porchestra_gaia2.yaml
```

`--dry-run` writes the resolved command without launching scenarios or calling
models. The runner sets PYTHONPATH so ARE loads the release's `sitecustomize.py`
and registers `porchestra`. For polling, SAE/revision ablations and standalone
ReAct controls, inspect the included registration and ablation modules before
changing configuration or environment variables.
