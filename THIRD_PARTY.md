# Third-party provenance

Reference: https://github.com/FoundationAgents/AOrchestra

Reference revision: `14a1a2051d6b03c479b706f8f555a60b8419e3b5`.

The reference repository uses Apache-2.0. Its complete license is preserved in
`licenses/AOrchestra-Apache-2.0.txt`. Existing source attribution is retained.
`requirements-upstream.txt` is copied from that reference revision.

The local `aorchestra`, `base` and benchmark adapters contain changes to model
configuration, proxy handling, memory, runners and evaluation. `porchestra`
adds proactive SAE control, active-session revision and compact working memory.
These descriptions are not a complete authorship or license determination:
verify the local source history and any additional origins before publication.

No vendored training frameworks, model weights or benchmark datasets are
included by the exporter. Installed dependencies retain their own licenses.

GAIA2 uses facebookresearch/meta-agents-research-environments at revision
`7946367413129784139e785ae4c351090002a0bb` (MIT). The local compatibility changes
are distributed as `integrations/are-compat.patch`; its upstream license is in
`licenses/ARE-MIT.txt`. See `GAIA2.md` for installation and reproduction limits.
