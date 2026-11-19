# GAIA2 trajectory browser

[PORCHESTRA trajectories](trajectories/README.md#porchestra) · [Claude Code trajectories](trajectories/claude-code/README.md)

Each collection contains 384 task trajectories across three rounds. PORCHESTRA includes 113 harness configuration updates. Claude Code includes agent messages, tool calls and returns, turn results, and four sub-agent sessions.

## Configuration history

Each task shows sub-agent revision requests, main-agent decisions, tool additions and removals, task and context changes, budget settings, and subsequent actions.

## Sub-agent execution

Use **Read the sub-agent execution traces** at the top of each task. Outputs and actions are shown directly; tool observations and context are expandable.

## Source records

Full configurations and execution records are organized into Markdown pages. The HTML/TXT download includes task pages, round indexes, and statistics. Open `gaia2_porch/index.html` after extraction.
