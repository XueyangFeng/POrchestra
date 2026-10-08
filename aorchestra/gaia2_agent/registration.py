"""Runtime registration for the ARE ``aorchestra`` agent."""

from __future__ import annotations

import os

from are.simulation.agents.are_simulation_agent_config import (
    ARESimulationReactAgentConfig,
    ARESimulationReactBaseAgentConfig,
    LLMEngineConfig,
)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def patch_are_builders() -> None:
    from are.simulation.agents.agent_builder import AgentBuilder
    from are.simulation.agents.agent_config_builder import AgentConfigBuilder

    if getattr(AgentBuilder, "_aorchestra_patched", False):
        return

    original_config_build = AgentConfigBuilder.build
    original_agent_build = AgentBuilder.build
    original_list_agents = AgentBuilder.list_agents

    def config_build(self, agent_name: str):
        if agent_name == "aorchestra":
            return ARESimulationReactAgentConfig(
                agent_name=agent_name,
                base_agent_config=ARESimulationReactBaseAgentConfig(
                    system_prompt="",
                    max_iterations=_env_int("AORCHESTRA_GAIA2_MAX_ITERATIONS", 300),
                ),
            )
        return original_config_build(self, agent_name)

    def list_agents(self):
        agents = list(original_list_agents(self))
        if "aorchestra" not in agents:
            agents.append("aorchestra")
        return agents

    def agent_build(self, agent_config, env=None, mock_responses=None):
        if agent_config.get_agent_name() != "aorchestra":
            return original_agent_build(self, agent_config, env, mock_responses)

        from aorchestra.gaia2_agent.agent import AOrchestraAREAgent

        assert env is not None, "Environment must be provided"
        assert env.time_manager is not None, "Time manager must be provided"
        assert env.append_to_world_logs is not None, "Log callback must be provided"

        base_config = agent_config.get_base_agent_config().llm_engine_config
        main_llm_engine = self.llm_engine_builder.create_engine(
            engine_config=base_config,
            mock_responses=mock_responses,
        )
        sub_llm_engine = _optional_engine(
            self,
            base_config,
            model_env="AORCHESTRA_SUB_MODEL",
            provider_env="AORCHESTRA_SUB_PROVIDER",
            endpoint_env="AORCHESTRA_SUB_ENDPOINT",
            mock_responses=mock_responses,
        ) or main_llm_engine
        sub_llm_engine = _with_sub_reasoning_effort(sub_llm_engine)
        summary_llm_engine = _optional_engine(
            self,
            base_config,
            model_env="AORCHESTRA_SUMMARY_MODEL",
            provider_env="AORCHESTRA_SUMMARY_PROVIDER",
            endpoint_env="AORCHESTRA_SUMMARY_ENDPOINT",
            mock_responses=mock_responses,
        ) or main_llm_engine

        agent_class = AOrchestraAREAgent
        extra = {}
        period = _env_int('AORCHESTRA_GAIA2_POLL_PERIOD',0)
        error_trigger = os.environ.get('AORCHESTRA_GAIA2_ERROR_TRIGGER') == '1'
        if period and error_trigger:
            raise ValueError('AOrchestra polling and error trigger are mutually exclusive')
        if period or error_trigger:
            from aorchestra.gaia2_agent.polling import AOrchestraPollingAREAgent
            from porchestra.gaia2_agent.llm_trace import LLMCallTrace, TracingLLMEngine
            from are.simulation.logging_config import get_logger_scenario_id
            trace=LLMCallTrace(get_logger_scenario_id() or 'unknown')
            main_llm_engine=TracingLLMEngine(main_llm_engine,trace,role='main_agent')
            sub_llm_engine=TracingLLMEngine(sub_llm_engine,trace,role='subagent')
            summary_llm_engine=TracingLLMEngine(summary_llm_engine,trace,role='summarizer')
            if period:
                agent_class=AOrchestraPollingAREAgent
                extra['poll_period']=period
            else:
                from aorchestra.gaia2_agent.error_trigger import AOrchestraErrorAREAgent
                agent_class=AOrchestraErrorAREAgent
        return agent_class(
            **extra,
            log_callback=env.append_to_world_logs,
            llm_engine=main_llm_engine,
            sub_llm_engine=sub_llm_engine,
            summary_llm_engine=summary_llm_engine,
            time_manager=env.time_manager,
            env=env,
            max_turns=agent_config.max_turns,
            max_attempts=_env_int("AORCHESTRA_GAIA2_MAX_ATTEMPTS", 10),
            max_total_steps=_env_int("AORCHESTRA_GAIA2_MAX_ITERATIONS", 300),
            default_subagent_steps=_env_int("AORCHESTRA_GAIA2_SUBAGENT_STEPS", 30),
            pause_env=env.pause,
            resume_env=env.resume_with_offset,
            simulated_generation_time_config=(
                agent_config.get_base_agent_config().simulated_generation_time_config
            ),
        )

    AgentConfigBuilder.build = config_build
    AgentBuilder.list_agents = list_agents
    AgentBuilder.build = agent_build
    AgentBuilder._aorchestra_patched = True


def _optional_engine(
    builder,
    base_config,
    *,
    model_env: str,
    provider_env: str,
    endpoint_env: str,
    mock_responses=None,
):
    model = os.environ.get(model_env)
    if not model:
        return None
    provider = os.environ.get(provider_env) or base_config.provider
    endpoint = os.environ.get(endpoint_env) or base_config.endpoint
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
            raise OSError("An AOrchestra OpenAI-compatible API key is required")
        engine = OpenAICompatEngine(
            model_config=OpenAICompatModelConfig(
                model_name=model,
                endpoint=endpoint,
                api_key=key,
            )
        )
        if mock_responses is not None:
            from are.simulation.agents.llm.llm_engine import MockLLMEngine

            return MockLLMEngine(mock_responses, engine)
        return engine

    return builder.llm_engine_builder.create_engine(
        engine_config=LLMEngineConfig(
            model_name=model,
            provider=provider,
            endpoint=endpoint,
        ),
        mock_responses=mock_responses,
    )


def _with_sub_reasoning_effort(engine):
    effort = os.environ.get("AORCHESTRA_GAIA2_SUB_REASONING_EFFORT")
    if not effort:
        return engine

    from are.simulation.agents.llm.openai_compat_engine import OpenAICompatEngine

    from mini_swe_gaia2.gaia2_agent.reasoning_engine import (
        ReasoningEffortOpenAICompatEngine,
    )

    if not isinstance(engine, OpenAICompatEngine):
        raise TypeError(
            "AORCHESTRA_GAIA2_SUB_REASONING_EFFORT requires an "
            "OpenAI-compatible SubAgent engine"
        )
    return ReasoningEffortOpenAICompatEngine(engine, effort)
