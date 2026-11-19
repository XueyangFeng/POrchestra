# GAIA2 trajectories

| System | Rounds | Trajectories | Browse |
| --- | ---: | ---: | --- |
| PORCHESTRA | 3 | 384 | [Configuration and execution](#porchestra) |
| Claude Code | 3 | 384 | [Execution traces](claude-code/README.md) |

## PORCHESTRA

Browse 384 trajectories across three rounds. Expand each trajectory to inspect requests, decisions, and configuration changes.



[Download the trajectories in HTML/TXT format](source/README.md).

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


