"""
Configuration loader for RLM - loads from .env file
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with default"""
    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable"""
    val = os.getenv(key, str(default)).lower()
    return val in ("true", "1", "yes")


def get_env_int(key: str, default: int = 0) -> int:
    """Get integer environment variable"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass
class LLMConfig:
    """Configuration for an LLM client"""
    provider: str
    base_url: str
    api_key: str
    model: str

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model": self.model
        }


@dataclass
class SafeguardsConfig:
    """Configuration for safeguards and limits"""
    max_iterations: int
    max_sub_llm_calls: int
    max_recursion_depth: int
    call_timeout: int
    total_timeout: int


@dataclass
class Config:
    """Main configuration class"""

    # LLM configs
    root_llm: LLMConfig
    sub_llm: LLMConfig

    # Mode
    default_mode: str  # 'repl' or 'tools'

    # Safeguards
    safeguards: SafeguardsConfig

    # Chunking
    default_chunk_size: int

    # Delays
    call_delay: int

    # Logging
    verbose: bool


def load_config() -> Config:
    """Load configuration from environment variables"""

    # ROOT LLM config
    root_llm = LLMConfig(
        provider=get_env("ROOT_PROVIDER", "vllm"),
        base_url=get_env("ROOT_BASE_URL", "http://localhost:8000/v1"),
        api_key=get_env("ROOT_API_KEY", "abc"),
        model=get_env("ROOT_MODEL", "openai/gpt-oss-20b")
    )

    # SUB LLM config (defaults to ROOT if not specified)
    sub_provider = get_env("SUB_PROVIDER") or root_llm.provider
    sub_base_url = get_env("SUB_BASE_URL") or root_llm.base_url
    sub_api_key = get_env("SUB_API_KEY") or root_llm.api_key
    sub_model = get_env("SUB_MODEL") or root_llm.model

    sub_llm = LLMConfig(
        provider=sub_provider,
        base_url=sub_base_url,
        api_key=sub_api_key,
        model=sub_model
    )

    # Safeguards
    safeguards = SafeguardsConfig(
        max_iterations=get_env_int("MAX_ITERATIONS", 30),
        max_sub_llm_calls=get_env_int("MAX_SUB_LLM_CALLS", 20),
        max_recursion_depth=get_env_int("MAX_RECURSION_DEPTH", 1),
        call_timeout=get_env_int("CALL_TIMEOUT", 60),
        total_timeout=get_env_int("TOTAL_TIMEOUT", 600)
    )

    return Config(
        root_llm=root_llm,
        sub_llm=sub_llm,
        default_mode=get_env("DEFAULT_MODE", "repl"),
        safeguards=safeguards,
        default_chunk_size=get_env_int("DEFAULT_CHUNK_SIZE", 4000),
        call_delay=get_env_int("CALL_DELAY", 0),
        verbose=get_env_bool("VERBOSE", False)
    )


# Global config instance
config = load_config()


# Convenience exports — use config.root_llm, config.safeguards, etc. directly
MAX_ITERATIONS = config.safeguards.max_iterations
MAX_SUB_LLM_CALLS = config.safeguards.max_sub_llm_calls
MAX_RECURSION_DEPTH = config.safeguards.max_recursion_depth
DEFAULT_CHUNK_SIZE = config.default_chunk_size
ROOT_LLM = config.root_llm.to_dict()
SUB_LLM = config.sub_llm.to_dict()
