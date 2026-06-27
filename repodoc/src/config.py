"""RepoDoc configuration."""

from dataclasses import dataclass
import os

# Token limit for clustering: skip LLM cluster when content is under this (CodeWiki default)
MAX_TOKEN_PER_MODULE = 36_369


@dataclass
class Config:
    """Configuration for RepoDoc."""

    repo_path: str
    output_dir: str = "output"
    dependency_graph_dir: str | None = None
    docs_dir: str | None = None
    max_depth: int = 2
    # LLM (Phase 2: clustering; Phase 3: doc generation)
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = "sk-1234"
    main_model: str = "deepseek-chat"
    cluster_model: str | None = None  # defaults to main_model
    # Optional LLM-based concept extraction (enhances keyword matching)
    llm_concept_extraction: bool = False  # set True for LLM-enhanced concept extraction
    llm_concept_max_components: int = 100  # max components to process with LLM (cost control)
    # Clustering robustness (tuned for local Ollama / lightweight models like qwen3)
    cluster_json_mode: bool = True  # use response_format json_object to force valid JSON
    cluster_max_workers: int = 1  # serialize batches (local single-inference setups)
    cluster_batch_size: int = 150  # components per LLM call (lower helps weak models follow format)
    # Disable qwen3-style "thinking" to save tokens and stick to the requested format.
    # None => auto-detect from model name (qwen3 => True, else False).
    disable_thinking: bool | None = None

    def __post_init__(self) -> None:
        if self.cluster_model is None:
            self.cluster_model = self.main_model
        if self.dependency_graph_dir is None:
            self.dependency_graph_dir = os.path.join(self.output_dir, "data")
        if self.docs_dir is None:
            repo_name = os.path.basename(os.path.normpath(self.repo_path))
            safe_name = "".join(c if c.isalnum() else "_" for c in repo_name)
            self.docs_dir = os.path.join(self.output_dir, "docs", f"{safe_name}-docs")
