from __future__ import annotations

from typing import Any, Dict, Optional
import base64
import os
from pathlib import Path
from openai import AsyncOpenAI 
from base.agent.base_action import BaseAction
from base.engine.async_llm import LLMsConfig, build_openai_client_kwargs


## Image Tools
class ImageAnalysisAction(BaseAction):
    name: str = "ImageAnalysisAction"
    description: str = (
        "Call the multimodal model to conduct image analysis via given queries. "
        "Uses model_config.yaml for API configuration."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Instruction or question describing what to analyze in the image",
            },
            "image_path": {
                "type": "string",
                "description": "Local file path or URL that points to the image resource",
            }
        },
        "required": ["query", "image_path"],
        "additionalProperties": False,
    }
    
    # Default model for image analysis (should support vision)
    DEFAULT_MODEL: str = "gpt-4o"

    def encode_image(self, image_path: str) -> str:
        data = Path(image_path).expanduser().read_bytes()
        return base64.b64encode(data).decode("utf-8")
    
    def _get_llm_config(self, model_name: Optional[str] = None) -> tuple:
        """Get LLM configuration from model_config.yaml or environment variables."""
        model_name = model_name or os.getenv("GAIA_VISION_MODEL") or self.DEFAULT_MODEL
        
        # Try to get config from LLMsConfig (model_config.yaml)
        try:
            llms_config = LLMsConfig.default()
            model_config = llms_config.get(model_name)
            if model_config:
                return (
                    model_config.key,
                    model_config.base_url,
                    model_config.model,
                )
        except Exception:
            pass
        
        # Fallback to environment variables
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://newapi.deepwisdom.ai/v1"
        
        return (api_key, base_url, model_name)

    async def __call__(self, **kwargs) -> Any:
        query = kwargs.get("query")
        image_path = kwargs.get("image_path")

        if not query or not image_path:
            return {"success": False, "output": None, "error": "Both query and image_path are required.", "metrics": {}}

        api_key, base_url, model = self._get_llm_config()
        if not api_key:
            return {"success": False, "output": None, "error": "No API key found. Configure in model_config.yaml or set OPENAI_API_KEY", "metrics": {}}

        try:
            from openai import AsyncOpenAI  # type: ignore
        except Exception:
            return {"success": False, "output": None, "error": "openai package not available", "metrics": {}}

        try:
            if image_path.startswith(("http://", "https://")):
                image_url = image_path
            else:
                encoded = self.encode_image(image_path)
                image_url = f"data:image/png;base64,{encoded}"
        except Exception as exc:
            return {"success": False, "output": None, "error": f"Failed to prepare image: {exc}", "metrics": {}}

        client = AsyncOpenAI(**build_openai_client_kwargs(api_key=api_key, base_url=base_url))
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": str(query)},
                ],
            }
        ]

        try:
            completion = await client.chat.completions.create(model=model, messages=messages)
        except Exception as exc:
            return {"success": False, "output": None, "error": f"Image analysis failed: {exc}", "metrics": {}}

        content = None
        try:
            if completion and completion.choices:
                content = completion.choices[0].message.content
        except Exception:
            content = None

        if not content:
            return {"success": False, "output": None, "error": "Model returned empty response", "metrics": {}}

        return {"success": True, "output": content.strip(), "error": None, "metrics": {}}

## Audio Tools
class ParseAudioAction(BaseAction):
    name: str = "ParseAudioAction"
    description: str = (
        "Transcribe an audio clip via OpenAI-compatible speech-to-text models. "
        "Uses model_config.yaml for API configuration."
    )
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Instruction that describes how to handle or summarize the audio content",
            },
            "audio_path": {
                "type": "string",
                "description": "Local file path that points to the audio resource (e.g. mp3, wav)",
            },
        },
        "required": ["query", "audio_path"],
        "additionalProperties": False,
    }
    
    # Default model for audio processing (should support audio input)
    DEFAULT_MODEL: str = "gpt-4o-transcribe"
    
    def _get_llm_config(self, model_name: Optional[str] = None) -> tuple:
        """Get LLM configuration from model_config.yaml or environment variables."""
        model_name = model_name or os.getenv("GAIA_AUDIO_MODEL") or self.DEFAULT_MODEL
        
        # Try to get config from LLMsConfig (model_config.yaml)
        try:
            llms_config = LLMsConfig.default()
            model_config = llms_config.get(model_name)
            if model_config:
                return (
                    model_config.key,
                    model_config.base_url,
                    model_config.model,
                )
        except Exception:
            pass
        
        # Fallback to environment variables
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://newapi.deepwisdom.ai/v1"
        
        return (api_key, base_url, model_name)

    async def __call__(self, **kwargs) -> Any:
        prompt = kwargs.get("query")
        audio_path = kwargs.get("audio_path")

        api_key, base_url, model = self._get_llm_config()
        if not api_key:
            return {
                "success": False,
                "output": None,
                "error": "No API key found. Configure in model_config.yaml or set OPENAI_API_KEY",
                "metrics": {},
            }

        try:
            client = AsyncOpenAI(**build_openai_client_kwargs(api_key=api_key, base_url=base_url))
            with open(audio_path, "rb") as audio_file:
                transcription = await client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    prompt=str(prompt),
                )
            transcript = getattr(transcription, "text", None) or str(transcription)
            return {"success": True, "output": transcript.strip(), "error": None, "metrics": {}}
        except Exception as first_exc:
            try:
                ext = audio_path.split(".")[-1].lower()
                with open(audio_path, "rb") as f:
                    encoded_audio = base64.b64encode(f.read()).decode("utf-8")
                client = AsyncOpenAI(**build_openai_client_kwargs(api_key=api_key, base_url=base_url))
                completion = await client.chat.completions.create(
                model=model,
                modalities=["text"],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": encoded_audio,
                                    "format": ext
                                }
                            }
                        ]
                    }
                ]
                )
                transcript = completion.choices[0].message.content
                return {"success": True, "output": transcript.strip(), "error": None, "metrics": {}}
            except Exception as second_exc:
                return {
                    "success": False,
                    "output": None,
                    "error": f"Audio processing failed: transcription={first_exc}; chat={second_exc}",
                    "metrics": {},
                }
