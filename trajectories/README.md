# GAIA2 harness configuration trajectories

Browse all trajectories directly on GitHub. No external website or JavaScript is required. Expand the details in each trajectory to inspect requests, decisions, and configuration changes.

The Markdown presentation records are sanitized. Provider identifiers, host-local paths, credentials, and known personal identifiers are removed or replaced. Task content and recorded configuration changes are retained.

[Download the original-format export](source_exports/README.md) for the supplied HTML/TXT layout with minimal privacy filtering. Its retained metadata differs from this presentation edition; see the export notes.

Every task has a prominent **Read the sub-agent execution traces** link. Dedicated execution pages show sub-agent outputs, reasoning, and tool actions directly, with expandable tool observations and context.

## Featured cases

- [Order cancellation: task, tool, and budget revision](round1/scenario_universe_25_dippkn/README.md)
- [Meeting cancellation: state handoff and event restoration](round1/scenario_universe_21_x1l1om/README.md)

## Rounds

| Round | Trajectories | With configuration updates | Updates | Correct |
| --- | ---: | ---: | ---: | ---: |
| [round1](round1/README.md) | 128 | 31 | 49 | 71 |
| [round2](round2/README.md) | 128 | 27 | 28 | 64 |
| [round3](round3/README.md) | 128 | 31 | 36 | 77 |

## Reading the records

Each trajectory shows the initial harness configuration, the sub-agent revision request, the corresponding main-agent decision, applied configuration differences, and subsequent actions. Full system configurations and every source event are available through Markdown links.

Configuration histories preserve session-local order; they do not reconstruct missing global timestamps or establish framework source-code changes. Budget fields retain their recorded meaning. Excerpts in summaries link to complete records.
