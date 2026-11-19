# GAIA2 trajectory browser

The static browser is in `docs/trajectories/`. Open `docs/index.html` locally or publish `docs/` with GitHub Pages. GitHub Pages publishes from the `main` branch and `/docs` directory. No custom workflow is required.

## Presentation and redactions

This release reorganizes supplied trajectory exports into configuration histories. Main-agent decisions are associated with configurations using the links in the supplied export. Session-local order is preserved; no global timestamps are invented.

All source links point to sanitized copies. Provider identifiers, host-local paths, credential patterns, and known personal identifiers are removed or replaced. Repeated host paths use stable placeholders. These public copies are not byte-for-byte originals. Benchmark task identities and observations remain part of the task records. Original archives are not included.

Configuration changes describe recorded task instructions, context, available tools, and budget fields. They do not establish framework source-code changes or independently verify enforcement. Budget fields retain their recorded meaning; cumulative and remaining budgets are not inferred.

## Repository integration

Copy `docs/trajectories/` into the intended repository. Preserve any existing `docs/index.html` and Pages workflow; integrate the new browser as a subdirectory if a site is already present. This bundle contains no Git history or personal Git configuration. Repository ownership and commit identity remain visible on GitHub and must be chosen separately.

GitHub Pages documentation: https://docs.github.com/en/get-started/start-your-journey/deploying-your-website-automatically
