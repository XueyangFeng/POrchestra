# Native Harness Adaptations for Benchmarks

This document describes task execution, task input, action spaces, native harness behavior, and execution budgets for Codex, Claude Code, and OpenCode. Each implementation uses the official CLI, which manages the execution loop, conversation history, and context compaction. The adaptation layer connects benchmark tasks and tools to the CLI and enforces execution budgets.

For GAIA1, GAIA2, and AutomationBench, MCP exposes the benchmark environment actions shared with the other baselines. Coding tasks use each CLI's native shell and file tools. Model responses, agent steps, agentic turns, and tool calls are counted according to their respective definitions.

## 1. Codex

All Codex adaptations use the official Codex CLI **v0.167.0**.

### 1.1 GAIA1

**Execution:** Tasks run through `codex exec --json --ephemeral`, with a separate session for each task.

**Task input:** The task set contains the 165 questions in GAIA 2023 validation. The question and paths to its attachments are passed as a user message through standard input. Context is not shared across tasks.

**Action space:** The shared GAIA tools are exposed through a per-task MCP service: `GoogleSearchAction`, `ExecuteCodeAction`, `ExtractUrlContentAction`, `ImageAnalysisAction`, `ParseAudioAction`, and `complete`. Only these tools are available. Native shell, web search, and project instruction loading are disabled. Python and Bash operations use the shared `ExecuteCodeAction`.

**Native behavior:** Codex retains its native default or fallback instructions, execution loop, conversation history, and context compaction. User configuration and rule files are ignored.

**Execution budget:** Each task allows up to 300 ordinary model responses, counting both completed and incomplete responses. A separate limit of 300 shared tool calls includes `complete`. The context window is 128,000 tokens, and the output limit is 8,192 tokens per response. Concurrency is 50, and the task timeout is 7,200 seconds. Standalone context compaction does not count as an ordinary task response.

### 1.2 GAIA2

**Execution:** Tasks run through `codex exec --json`. Later user turns resume the same session through `codex exec resume`.

**Task input:** The task set is the fixed mini128 subset excluding Ambiguity scenarios. ARE loads each scenario. The task description, scenario start time, additional scenario instructions, and application interaction rules are passed as user input through standard input. New user messages and environment notifications enter the native conversation through MCP tool results or subsequent user input. Notifications already incorporated into the history are not appended again. The adaptation supports text scenarios.

**Action space:** The scenario's actual `AppToolAdapter` instances are exposed as MCP tools, preserving argument types, optional arguments, and defaults. The ARE executor invokes the tools sequentially. Only GAIA2 application tools are available. Native shell, web search, apps, plugins, memories, skills, and project instruction loading are disabled.

**Native behavior:** The CLI retains its native default or fallback instructions, execution loop, history, and context compaction. No replacement agent or planner prompt is configured. Notifications and tool results enter the native conversation, and the CLI manages compaction.

**Execution budget:** All user turns within a scenario share a budget of 300 completed task-model responses. Resuming a session does not reset this budget, and one response may contain multiple tool calls. Transport failures and context compaction do not consume task-response steps. The context window is 128,000 tokens. Concurrency is 50, the scenario timeout is 14,400 seconds, and the outer loop has an additional 600-second no-progress limit.

### 1.3 AutomationBench

**Execution:** Tasks run through `codex exec --json --ephemeral`, with a separate session for each task.

**Task input:** The fixed auto_mini subset contains 20 tasks from each of six public domains, for 120 tasks in total. The adaptation extracts the official task's system and user content. User content is passed through standard input; system content is written to `system.txt` and supplied to the CLI through `model_instructions_file` and `base_instructions`.

**Action space:** Official business tools are exposed through a per-task MCP service using their official names, descriptions, and JSON Schemas. The `zapier` toolset provides `search_tools` and `execute_tool`; `limited_zapier` directly exposes the named tools permitted for the task. Only `mcp__automation__*` business tools are available. Native shell, web search, apps, plugins, memories, and project instruction loading are disabled, and the CLI uses a read-only sandbox. Tool actions operate in a separate simulated business world for each task.

**Native behavior:** The official task's system content explicitly supplies the CLI instructions. The native CLI manages the execution loop, runtime messages, tool-result wrapping, conversation history, and context compaction. Tasks use separate sessions and do not resume another task's history.

**Execution budget:** Each task allows up to 300 ordinary model responses, counting both completed and incomplete responses. Once the limit is reached, the next ordinary task request is rejected. Standalone context compaction is excluded from this budget. The context window is 128,000 tokens, the output limit is 8,192 tokens per response, and the content truncation setting is 10,000 tokens. Concurrency is 50, and the task timeout is 7,200 seconds. Compaction thresholds and reasoning effort retain their default settings.

### 1.4 SWE-bench

**Execution:** Tasks run through `codex exec --json`, with a separate session for each task.

**Task input:** Tasks come from the fixed same100 subset of SWE-bench Verified. The repository name, issue description, working directory, and testing conditions are assembled into task text and passed through standard input.

**Action space:** Native shell and file tools are available in a separate task container, allowing the model to inspect the repository, modify code, and run tests. The CLI uses `danger-full-access` and `approval_policy="never"`. Web search is disabled, and user configuration and rules are ignored.

**Native behavior:** The CLI manages the execution loop, tool calls, history, and context compaction. The model catalog supplies the general coding instruction `Help the user with their coding tasks. Inspect the repository with tools and verify results.`, declares the `shell_command` tool type, and sets the supported reasoning-level list to empty.

**Execution budget:** Each task allows up to 500 completed tool calls. The adaptation counts `command_execution`, `file_change`, and `mcp_tool_call` items in `item.completed` events, deduplicating by item ID, and terminates inference when the limit is reached. The context window is 128,000 tokens, the content truncation setting is 10,000 tokens, and the native CLI manages output length. Concurrency is 50, and the inference timeout is 7,200 seconds.

### 1.5 DeepSWE

**Execution:** The task set contains the 113 tasks in DeepSWE v1.1. Pier v0.3.1 invokes `codex exec --json`.

**Task input:** Each task's original `instruction.md` is passed directly to the CLI as the user task. Tasks use separate sessions.

**Action space:** Native shell and file tools are available in a separate task container for inspecting the repository, modifying code, and running tests. The CLI uses `--dangerously-bypass-approvals-and-sandbox`, `--skip-git-repo-check`, and `--enable unified_exec`. Web search is disabled.

**Native behavior:** The CLI manages instructions, the execution loop, tool calls, history, and context compaction. Tasks are passed directly to the CLI without a replacement system prompt.

**Execution budget:** No additional common model-step or tool-call limit is imposed; execution is bounded by a 10,800-second task timeout. Reasoning effort is medium. The context window and output length retain native settings. Concurrency is 50.

## 2. Claude Code

Both Claude Code adaptations use the official Claude Code CLI **v2.1.311**.

### 2.1 GAIA1

**Execution:** Tasks run through `claude --print --verbose --output-format stream-json`, with a separate session for each task.

**Task input:** The task set contains the 165 questions in GAIA 2023 validation. The question and paths to its attachments are passed as a user message through standard input. Context is not shared across tasks.

**Action space:** The shared GAIA tools are exposed through a per-task MCP service: `GoogleSearchAction`, `ExecuteCodeAction`, `ExtractUrlContentAction`, `ImageAnalysisAction`, `ParseAudioAction`, and `complete`. Built-in tools are disabled through `--tools ''`, only `mcp__gaia__*` tools are allowed, and `--strict-mcp-config` restricts tool loading to the task configuration. Python and Bash operations use the shared `ExecuteCodeAction`.

**Native behavior:** The CLI retains its native instructions, execution loop, conversation history, and context management. User and project settings are not loaded, and custom commands and session persistence are disabled. Each task starts a new session without resuming another task's conversation.

**Execution budget:** The CLI uses `--max-turns 300`, with a separate limit of 300 shared tool calls, including `complete`. The native CLI manages the context window. Concurrency is 10, and the task timeout is 7,200 seconds.

### 2.2 GAIA2

**Execution:** Tasks run through `claude --print --bare --verbose --output-format stream-json`. Later user turns resume the same session through `--resume`.

**Task input:** The task set is the fixed mini128 subset excluding Ambiguity scenarios. ARE loads each scenario. The task description, scenario start time, additional scenario instructions, and application interaction rules are passed as user input through standard input. New user messages and environment notifications enter the native conversation through MCP tool results or subsequent user input. Notifications already incorporated into the history are not appended again. The adaptation supports text scenarios.

**Action space:** The scenario's actual `AppToolAdapter` instances are exposed as MCP tools, preserving argument types, optional arguments, and defaults. The ARE executor invokes the tools sequentially. Built-in tools are disabled, only `mcp__gaia2__*` tools are allowed, and `--strict-mcp-config` restricts tool loading to the task configuration.

**Native behavior:** The CLI retains its native instructions, execution loop, conversation history, and context management. No replacement agent or planner prompt is configured. User and project settings are not loaded. Notifications and tool results enter the native conversation, and subsequent user turns continue in the same session.

**Execution budget:** All user turns within a scenario share a budget of 300 completed task-model responses, which is not reset when the session resumes. The CLI also uses `--max-turns 300`. Transport failures, token counting, and context compaction do not consume the shared task-response budget. The native CLI manages the context window. Concurrency is 50, the scenario timeout is 14,400 seconds, and the outer loop has an additional 600-second no-progress limit.

## 3. OpenCode

All OpenCode adaptations use the official OpenCode CLI **v1.19.5**.

### 3.1 GAIA1

**Execution:** Tasks run through `opencode run --pure --auto --format json --agent build`, using the native build agent.

**Task input:** The task set contains the 165 questions in GAIA 2023 validation. The question and paths to its attachments are passed as a command-line user message. Each task starts a separate session, and context is not shared across tasks.

**Action space:** The shared GAIA tools are exposed through a per-task MCP service: `GoogleSearchAction`, `ExecuteCodeAction`, `ExtractUrlContentAction`, `ImageAnalysisAction`, `ParseAudioAction`, and `complete`. Permissions deny tools by default and allow only `gaia_*` tools. Python and Bash operations use the shared `ExecuteCodeAction`.

**Native behavior:** The native build agent's instructions are retained without a replacement system prompt. OpenCode manages the execution loop, tool-result handling, conversation history, and context compaction.

**Execution budget:** The build agent uses `steps=300`, with a separate limit of 300 shared tool calls, including `complete`. The context window is 128,000 tokens, and the output limit is 8,192 tokens per response. Concurrency is 50, and the task timeout is 7,200 seconds. Auxiliary requests such as title generation are distinct from native agent steps.

### 3.2 GAIA2

**Execution:** Tasks run through `opencode run --pure --auto --format json --agent build`. Later user turns resume the same session through `--session`.

**Task input:** The task set is the fixed mini128 subset excluding Ambiguity scenarios. ARE loads each scenario. The task description, scenario start time, additional scenario instructions, and application interaction rules are passed as a command-line user message. New user messages and environment notifications enter the native conversation through MCP tool results or subsequent user input. Notifications already incorporated into the history are not appended again. The adaptation supports text scenarios.

**Action space:** The scenario's actual `AppToolAdapter` instances are exposed as MCP tools, preserving argument types, optional arguments, and defaults. The ARE executor invokes the tools sequentially. Permissions deny tools by default and allow only `gaia2_*` application tools.

**Native behavior:** The CLI retains the native build agent's instructions, execution loop, conversation history, and context compaction. No replacement agent or planner prompt is configured. Notifications and tool results enter the native conversation, and the CLI manages auxiliary operations such as title generation and compaction.

**Execution budget:** All user turns within a scenario share a budget of 300 completed task-model responses, which is not reset when the session resumes. The build agent also uses `steps=300`. Transport failures, title generation, and context compaction do not consume the shared task-response budget. The context window is 128,000 tokens, and the output limit is 8,192 tokens per response. Concurrency is 50, the scenario timeout is 14,400 seconds, and the outer loop has an additional 600-second no-progress limit.

### 3.3 AutomationBench

**Execution:** Tasks run through `opencode run --pure --auto --format json --agent automation`, using the automation primary agent.

**Task input:** The fixed auto_mini subset contains 20 tasks from each of six public domains, for 120 tasks in total. The official task's system content is assigned to `agent.automation.prompt`, and the remaining task messages are combined into a command-line user message.

**Action space:** Official business tools are exposed through a per-task MCP service using their official names, descriptions, and JSON Schemas. The adaptation supports `zapier`, `limited_zapier`, and the official `api` toolset. Permissions use `"*": "deny"` and `"automation_*": "allow"`, exposing only the business tools permitted for the task. Actions operate in a separate simulated business world for each task.

**Native behavior:** The official task's system content configures the automation agent. OpenCode manages the execution loop, tool calls, history, and context compaction. Tasks use separate sessions without resuming another task's history.

**Execution budget:** The automation agent uses `agent.automation.steps=300`, with steps counted through native `step_finish` events. The context window is 128,000 tokens, and the output limit is 8,192 tokens per response. Concurrency is 50, and the task timeout is 7,200 seconds. Temperature, top_p, and reasoning effort retain their default settings.

### 3.4 SWE-bench

**Execution:** Tasks run through `opencode run --pure --auto --format json --agent build`, using the native build agent.

**Task input:** Tasks come from the fixed same100 subset of SWE-bench Verified. The repository name, issue description, working directory, and testing conditions are assembled into task text and attached through `--file`. Each task uses a separate session.

**Action space:** Native development tools are available in a separate task container. Permissions deny tools by default and explicitly allow `bash`, `read`, `edit`, `glob`, `grep`, and `todowrite`.

**Native behavior:** The native build agent's instructions are retained. OpenCode manages tool execution, conversation history, and context compaction.

**Execution budget:** The build agent uses `steps=500`, `temperature=0`, and `top_p=1`. The context window is 128,000 tokens, and the output limit is 8,192 tokens per response. Concurrency is 50, and the inference timeout is 7,200 seconds.

### 3.5 DeepSWE

**Execution:** The task set contains the 113 tasks in DeepSWE v1.1. Pier v0.3.1 invokes `opencode --model=... run --format=json --variant medium --thinking --auto -- <instruction>`.

**Task input:** Each task's original `instruction.md` is passed to the CLI as a user message through `-- <instruction>`. Tasks use separate sessions.

**Action space:** Native shell and file tools are available in a separate task container for inspecting the repository, modifying code, and running tests.

**Native behavior:** The native build agent manages instructions, tool calls, history, and context compaction. Tasks are passed directly to the CLI without a replacement system prompt.

**Execution budget:** No additional build-step limit is imposed; execution is bounded by a 10,800-second task timeout. The context window is 128,000 tokens, and the output limit is 32,768 tokens per response. The CLI uses the medium variant with `reasoningEffort: medium`. Concurrency is 50.
