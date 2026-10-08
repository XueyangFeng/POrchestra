"""Runtime registration for the ARE ``porchestra`` agent."""

from __future__ import annotations

import os
from typing import Any

from are.simulation.agents.are_simulation_agent_config import (
    ARESimulationReactAgentConfig,
    ARESimulationReactBaseAgentConfig,
    LLMEngineConfig,
)


PSUB_REACT_AGENT_NAME = "porchestra_subagent_react"
PORCHESTRA_FAIR_REACT_AGENT_NAME = "porchestra_fair_react"
STANDALONE_REACT_AGENT_NAMES = {
    PSUB_REACT_AGENT_NAME,
    PORCHESTRA_FAIR_REACT_AGENT_NAME,
}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _build_sub_llm_engine(
    builder: Any,
    *,
    base_config: LLMEngineConfig,
    mock_responses: list[str] | None,
):
    sub_model = os.environ.get("PORCHESTRA_SUB_MODEL")
    if not sub_model:
        return None

    provider = os.environ.get("PORCHESTRA_SUB_PROVIDER") or base_config.provider
    endpoint = os.environ.get("PORCHESTRA_SUB_ENDPOINT") or base_config.endpoint
    if provider == "llama-api" and endpoint:
        from are.simulation.agents.llm.openai_compat_engine import (
            OpenAICompatEngine,
            OpenAICompatModelConfig,
        )

        key = (
            os.environ.get("LLAMA_API_KEY")
            or os.environ.get("OPENAI_COMPAT_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        if not key:
            raise EnvironmentError("A SubAgent OpenAI-compatible API key is required")
        engine = OpenAICompatEngine(
            model_config=OpenAICompatModelConfig(
                model_name=sub_model,
                endpoint=endpoint,
                api_key=key,
            )
        )
        if mock_responses is not None:
            from are.simulation.agents.llm.llm_engine import MockLLMEngine

            return MockLLMEngine(mock_responses, engine)
        return engine

    return builder.create_engine(
        engine_config=LLMEngineConfig(
            model_name=sub_model,
            provider=provider,
            endpoint=endpoint,
        ),
        mock_responses=mock_responses,
    )
def patch_are_builders() -> None:
    from are.simulation.agents.agent_builder import AgentBuilder
    from are.simulation.agents.agent_config_builder import AgentConfigBuilder

    if getattr(AgentBuilder, "_porchestra_patched", False):
        return

    original_config_build = AgentConfigBuilder.build
    original_agent_build = AgentBuilder.build
    original_list_agents = AgentBuilder.list_agents

    def config_build(self, agent_name: str):
        max_iterations = _env_int("PORCHESTRA_GAIA2_MAX_ITERATIONS", 300)
        if agent_name == "porchestra":
            return ARESimulationReactAgentConfig(
                agent_name=agent_name,
                base_agent_config=ARESimulationReactBaseAgentConfig(
                    system_prompt="",
                    max_iterations=max_iterations,
                ),
            )
        if agent_name in STANDALONE_REACT_AGENT_NAMES:
            from porchestra.gaia2_agent.prompts import (
                PORCHESTRA_FAIR_REACT_PROMPT,
                PSUB_REACT_PROMPT,
            )

            prompt = (
                PORCHESTRA_FAIR_REACT_PROMPT
                if agent_name == PORCHESTRA_FAIR_REACT_AGENT_NAME
                else PSUB_REACT_PROMPT
            )

            return ARESimulationReactAgentConfig(
                agent_name=agent_name,
                base_agent_config=ARESimulationReactBaseAgentConfig(
                    system_prompt=prompt,
                    max_iterations=max_iterations,
                ),
            )
        config = original_config_build(self, agent_name)
        try:
            config.get_base_agent_config().max_iterations = max_iterations
        except Exception:
            pass
        return config

    def list_agents(self):
        agents = list(original_list_agents(self))
        for agent_name in ("porchestra", *STANDALONE_REACT_AGENT_NAMES):
            if agent_name not in agents:
                agents.append(agent_name)
        return agents

    def agent_build(self, agent_config, env=None, mock_responses=None):
        agent_name = agent_config.get_agent_name()
        if agent_name not in {"porchestra", *STANDALONE_REACT_AGENT_NAMES}:
            return original_agent_build(self, agent_config, env, mock_responses)

        if agent_name in STANDALONE_REACT_AGENT_NAMES:
            from are.simulation.agents.default_agent.agent_factory import (
                are_simulation_react_json_agent,
            )
            from are.simulation.agents.default_agent.are_simulation_main import (
                ARESimulationAgent,
            )

            assert env is not None, "Environment must be provided"
            assert env.time_manager is not None, "Time manager must be provided"
            assert env.append_to_world_logs is not None, "Log callback must be provided"

            llm_engine = self.llm_engine_builder.create_engine(
                engine_config=agent_config.get_base_agent_config().llm_engine_config,
                mock_responses=mock_responses,
            )
            return ARESimulationAgent(
                log_callback=env.append_to_world_logs,
                llm_engine=llm_engine,
                base_agent=are_simulation_react_json_agent(
                    llm_engine=llm_engine,
                    base_agent_config=agent_config.get_base_agent_config(),
                ),
                time_manager=env.time_manager,
                max_turns=agent_config.max_turns,
                pause_env=env.pause,
                resume_env=env.resume_with_offset,
                simulated_generation_time_config=(
                    agent_config.get_base_agent_config().simulated_generation_time_config
                ),
            )

        from porchestra.gaia2_agent.agent import POrchestraAREAgent

        assert env is not None, "Environment must be provided"
        assert env.time_manager is not None, "Time manager must be provided"
        assert env.append_to_world_logs is not None, "Log callback must be provided"

        llm_engine = self.llm_engine_builder.create_engine(
            engine_config=agent_config.get_base_agent_config().llm_engine_config,
            mock_responses=mock_responses,
        )
        base_config = agent_config.get_base_agent_config().llm_engine_config
        sub_llm_engine = _build_sub_llm_engine(
            self.llm_engine_builder,
            base_config=base_config,
            mock_responses=mock_responses,
        ) or llm_engine
        from porchestra.gaia2_agent.llm_trace import LLMCallTrace, TracingLLMEngine

        from are.simulation.logging_config import get_logger_scenario_id

        scenario_id = get_logger_scenario_id() or "unknown"
        trace = LLMCallTrace(scenario_id)
        main_traced_engine = TracingLLMEngine(
            llm_engine,
            trace,
            role="main_agent",
        )
        sub_traced_engine = TracingLLMEngine(
            sub_llm_engine,
            trace,
            role="subagent",
        )
        agent = POrchestraAREAgent(
            log_callback=env.append_to_world_logs,
            llm_engine=main_traced_engine,
            sub_llm_engine=sub_traced_engine,
            time_manager=env.time_manager,
            env=env,
            max_turns=agent_config.max_turns,
            max_total_steps=_env_int("PORCHESTRA_GAIA2_MAX_ITERATIONS", 300),
            default_subagent_steps=_env_int("PORCHESTRA_GAIA2_SUBAGENT_STEPS", 30),
            poll_period=_env_int("PORCHESTRA_GAIA2_POLL_PERIOD", 0),
            pause_env=env.pause,
            resume_env=env.resume_with_offset,
            simulated_generation_time_config=(
                agent_config.get_base_agent_config().simulated_generation_time_config
            ),
        )
        main_traced_engine.context_provider = agent.llm_trace_context
        sub_traced_engine.context_provider = agent.llm_trace_context
        return agent

    AgentConfigBuilder.build = config_build
    AgentBuilder.list_agents = list_agents
    AgentBuilder.build = agent_build
    AgentBuilder._porchestra_patched = True
