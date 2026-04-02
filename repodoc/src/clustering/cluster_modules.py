"""Cluster leaf components into a module tree via LLM."""

import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from src.analysis.models.core import Node
from src.config import Config, MAX_TOKEN_PER_MODULE
from src.utils import count_tokens
from src.llm import call_llm
from src.clustering.prompts import format_cluster_prompt

logger = logging.getLogger(__name__)

# Maximum components per batch to avoid token limit
MAX_COMPONENTS_PER_BATCH = 150
# Max concurrent LLM calls for batch clustering (avoid rate limits)
MAX_BATCH_WORKERS = 16
# Only skip clustering when content is small AND we have few leaves (avoid one big module for medium projects)
SKIP_CLUSTER_MAX_LEAVES = 12


def format_potential_core_components(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    include_code: bool = False,
) -> str:
    """Format leaf components for the cluster prompt (with or without code)."""
    valid_leaf_nodes = [n for n in leaf_nodes if n in components]
    for n in leaf_nodes:
        if n not in components:
            logger.warning(
                "Skipping invalid leaf node '%s' - not found in components", n
            )

    by_file: Dict[str, List[str]] = defaultdict(list)
    for n in valid_leaf_nodes:
        by_file[components[n].relative_path].append(n)

    lines = []
    for file, nodes in sorted(by_file.items()):
        lines.append(f"# {file}")
        for n in nodes:
            lines.append(f"  - {n}")
            if include_code:
                code = components[n].source_code or ""
                if code:
                    # Include only first 500 chars of code to save tokens
                    lines.append(f"    ```\n    {code[:500]}\n    ```")

    return "\n".join(lines)


def parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse LLM response to extract grouped components."""
    if (
        "<GROUPED_COMPONENTS>" not in response
        or "</GROUPED_COMPONENTS>" not in response
    ):
        raise ValueError("Missing GROUPED_COMPONENTS tags")

    content = response.split("<GROUPED_COMPONENTS>")[1].split("</GROUPED_COMPONENTS>")[
        0
    ]

    # Clean up the content - remove any leading/trailing whitespace
    content = content.strip()

    # Handle potential markdown code blocks
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    elif content.startswith("{"):
        pass

    try:
        module_tree = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in LLM response: {e}")

    if not isinstance(module_tree, dict):
        raise ValueError(f"Expected dict, got {type(module_tree)}")

    return module_tree


def call_llm_with_retry(
    prompt: str,
    config: Config,
    max_retries: int = 2,
) -> Tuple[str, Dict[str, Any]]:
    """Call LLM with retry on parse failure, using lower temperature."""
    last_error = None
    last_response = ""

    for attempt in range(max_retries):
        try:
            # Use lower temperature on retry to get more structured output
            temperature = 0.0 if attempt == 0 else 0.1
            last_response, _ = call_llm(
                prompt, config, model=config.cluster_model, temperature=temperature
            )

            module_tree = parse_llm_response(last_response)
            return last_response, module_tree

        except Exception as e:
            last_error = e
            logger.warning(
                f"Attempt {attempt + 1} failed: {e}. Response preview: {last_response[:200] if last_response else 'N/A'}"
            )
            continue

    raise ValueError(f"Failed after {max_retries} attempts: {last_error}")


def _cluster_one_batch(
    idx: int,
    batch: List[str],
    components: Dict[str, Node],
    config: Config,
) -> Dict[str, Any]:
    """Process a single batch (used by parallel executor). Returns module_tree or fallback dict."""
    potential = format_potential_core_components(
        batch, components, include_code=False
    )
    prompt = format_cluster_prompt(potential)
    try:
        _, module_tree = call_llm_with_retry(prompt, config)
        logger.info(f"Batch {idx + 1} completed: {len(module_tree)} modules")
        return module_tree
    except Exception as e:
        logger.error(f"Batch {idx + 1} failed: {e}")
        return {f"batch_{idx + 1}": {"path": ".", "components": batch}}


def cluster_components_batch(
    components_to_cluster: List[str],
    components: Dict[str, Node],
    config: Config,
    batch_size: int = MAX_COMPONENTS_PER_BATCH,
) -> Dict[str, Any]:
    """Cluster a list of components using batched LLM calls (parallel when multiple batches)."""
    if not components_to_cluster:
        return {}

    total = len(components_to_cluster)
    logger.info(f"Batching {total} components into groups of {batch_size}")

    # Split into batches
    batches = []
    for i in range(0, total, batch_size):
        batches.append(components_to_cluster[i : i + batch_size])

    num_batches = len(batches)
    workers = min(MAX_BATCH_WORKERS, num_batches)
    batch_results: List[Dict[str, Any]] = [{}] * num_batches  # placeholder

    if num_batches == 1:
        batch_results[0] = _cluster_one_batch(0, batches[0], components, config)
    else:
        logger.info(f"Processing {num_batches} batches with {workers} workers")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_idx = {
                executor.submit(
                    _cluster_one_batch, idx, batch, components, config
                ): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    batch_results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Batch {idx + 1} failed: {e}")
                    batch_results[idx] = {
                        f"batch_{idx + 1}": {"path": ".", "components": batches[idx]}
                    }

    # Merge all batch results
    merged: Dict[str, Any] = {}
    for result in batch_results:
        if isinstance(result, dict):
            merged.update(result)

    return merged


def cluster_modules(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    config: Config,
    current_module_tree: dict[str, Any] | None = None,
    current_module_name: str | None = None,
    current_module_path: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Cluster leaf components into a module tree using LLM.
    Returns a dict: module_name -> { "path", "components", "children" }.
    """
    current_module_tree = current_module_tree or {}
    current_module_path = current_module_path or []

    # If too many leaf nodes, use batch clustering
    if len(leaf_nodes) > MAX_COMPONENTS_PER_BATCH:
        return _cluster_large_set(
            leaf_nodes, components, config, current_module_tree, current_module_path
        )

    return _cluster_small_set(
        leaf_nodes, components, config,
        current_module_tree, current_module_name, current_module_path
    )


def _cluster_large_set(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    config: Config,
    current_module_tree: dict[str, Any],
    current_module_path: List[str],
) -> Dict[str, Any]:
    """Handle clustering for large sets (> MAX_COMPONENTS_PER_BATCH)."""
    logger.info(
        f"Large module detected ({len(leaf_nodes)} components), using batch clustering"
    )

    valid_leaf_nodes = [n for n in leaf_nodes if n in components]
    module_tree = cluster_components_batch(valid_leaf_nodes, components, config)

    if not module_tree:
        logger.warning("Batch clustering returned empty result")
        return {}

    if not current_module_tree:
        current_module_tree.update(module_tree)

    # Recursively cluster each module's components
    for module_name, module_info in list(module_tree.items()):
        sub_leaf = module_info.get("components", [])
        valid_sub = [n for n in sub_leaf if n in components]

        if len(valid_sub) > MAX_COMPONENTS_PER_BATCH:
            module_info["children"] = cluster_modules(
                valid_sub, components, config,
                current_module_tree, module_name, current_module_path + [module_name]
            )
        else:
            module_info["children"] = {}

    return module_tree


def _cluster_small_set(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    config: Config,
    current_module_tree: dict[str, Any],
    current_module_name: str | None,
    current_module_path: List[str],
) -> Dict[str, Any]:
    """Handle clustering for smaller sets (<= MAX_COMPONENTS_PER_BATCH)."""
    potential = format_potential_core_components(leaf_nodes, components, include_code=False)
    potential_with_code = format_potential_core_components(leaf_nodes, components, include_code=True)
    token_count = count_tokens(potential_with_code)

    # Skip clustering for small content
    if token_count <= MAX_TOKEN_PER_MODULE and len(leaf_nodes) <= SKIP_CLUSTER_MAX_LEAVES:
        return _build_simple_module_tree(
            leaf_nodes, components, current_module_tree, current_module_name
        )

    # Call LLM for clustering
    prompt = format_cluster_prompt(potential, current_module_tree, current_module_name)
    module_tree = _call_clustering_llm(prompt, config, current_module_name)
    if not module_tree:
        return {}

    return _process_clustering_results(
        module_tree, components, config,
        current_module_tree, current_module_path
    )


def _build_simple_module_tree(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    current_module_tree: dict[str, Any],
    current_module_name: str | None,
) -> Dict[str, Any]:
    """Build a simple module tree when clustering is skipped."""
    logger.debug(
        "Skipping clustering for %s: token count and leaf count under threshold",
        current_module_name,
    )
    if not current_module_tree:
        module_path = "."
        if leaf_nodes and leaf_nodes[0] in components:
            module_path = components[leaf_nodes[0]].relative_path or "."
        repo_name = current_module_name or "root"
        return {
            repo_name: {
                "path": module_path,
                "components": leaf_nodes,
                "children": {},
            }
        }
    return {}


def _call_clustering_llm(
    prompt: str,
    config: Config,
    current_module_name: str | None,
) -> Dict[str, Any] | None:
    """Call LLM for clustering with retry logic."""
    response = ""
    try:
        response, module_tree = call_llm_with_retry(prompt, config)
    except Exception as e:
        logger.error(
            "Failed to cluster modules after retries: %s. Response: %s...",
            e,
            response[:200] if response else "N/A",
        )
        return None

    if len(module_tree) <= 1:
        logger.debug(
            "Skipping clustering for %s: module tree too small (%s modules)",
            current_module_name,
            len(module_tree),
        )
        return None

    return module_tree


def _process_clustering_results(
    module_tree: Dict[str, Any],
    components: Dict[str, Node],
    config: Config,
    current_module_tree: dict[str, Any],
    current_module_path: List[str],
) -> Dict[str, Any]:
    """Process clustering results and recurse into sub-modules."""
    if not current_module_tree:
        current_module_tree.update(module_tree)
    else:
        # Navigate to the correct nested position
        value = current_module_tree
        for key in current_module_path:
            value = value[key]["children"]
        # Merge new modules
        for name, info in module_tree.items():
            info.pop("path", None)
            value[name] = info

    # Recurse into each module's sub-components
    for module_name, module_info in module_tree.items():
        sub_leaf = module_info.get("components", [])
        valid_sub = [n for n in sub_leaf if n in components]

        for n in sub_leaf:
            if n not in components:
                logger.warning(
                    "Skipping invalid sub leaf node '%s' in module '%s'", n, module_name
                )

        module_info["children"] = cluster_modules(
            valid_sub, components, config,
            current_module_tree, module_name, current_module_path + [module_name]
        )

    return module_tree
