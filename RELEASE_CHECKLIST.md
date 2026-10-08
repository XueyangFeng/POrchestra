# Before publication

- Select a license for original POrchestra contributions and add the root LICENSE.
- Confirm source ownership and third-party provenance; preserve required notices.
- Review every exported file and its provenance manifest for credentials,
  internal endpoints, local paths and unrelated code.
- Install dependencies in a fresh Python environment and resolve version conflicts.
- Run both entrypoints with `--help` and verify one authorized GAIA/SWE-bench task.
- Check GAIA2 ARE patch application, registration and dry-run; validate an
  authorized scenario in a fresh ARE environment before claiming reproduction.
- Document extra tools or libraries required for multimodal GAIA tasks.
- Keep benchmark datasets, downloaded content, logs and checkpoints out of Git.
- If publishing existing Git history, audit every revision separately. The exporter
  creates a source snapshot without Git history and does not audit the old history.
