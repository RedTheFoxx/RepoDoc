"""Module clustering: group leaf components into modules via LLM."""

from src.clustering.cluster_modules import (
    format_potential_core_components,
    cluster_modules,
)

__all__ = ["format_potential_core_components", "cluster_modules"]
