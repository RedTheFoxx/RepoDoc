"""Cluster leaf components into a module tree via LLM.

Tuned to be robust with lightweight local models (e.g. qwen3 via Ollama):
- tolerant JSON parsing (optional <GROUPED_COMPONENTS> tags, qwen3 thinking stripped),
- progressive retry strategies (JSON mode -> tags fallback),
- serialized batches for single-inference setups,
- heuristic directory-based fallback when the LLM ultimately fails.
"""

import json
import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from src.analysis.models.core import Node
from src.config import Config, MAX_TOKEN_PER_MODULE
from src.utils import count_tokens
from src.llm import call_llm
from src.clustering.prompts import format_cluster_prompt

logger = logging.getLogger(__name__)

# Fallback batch size when config.cluster_batch_size is unavailable
MAX_COMPONENTS_PER_BATCH = 150
# Only skip clustering when content is small AND we have few leaves (avoid one big module for medium projects)
SKIP_CLUSTER_MAX_LEAVES = 12

# qwen3-style reasoning block: <think>...</think>
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
# Markdown code fence (json or plain)
_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


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


def _strip_thinking(text: str) -> str:
    """Remove qwen3-style reasoning blocks and stray think tags."""
    text = _THINK_PATTERN.sub("", text)
    # Remove any leftover think tags (unbalanced) and the /no_think control token
    for tag in ("<think>", "</think>"):
        text = text.replace(tag, "")
    return text.strip()


def _extract_json_object(text: str) -> str:
    """Return the substring spanning the first '{' to the last '}'."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No '{' found in response")
    end = text.rfind("}")
    if end == -1 or end < start:
        raise ValueError("No matching '}' found in response")
    return text[start : end + 1]


def _build_name_index(
    ids: List[str], components: Dict[str, Node]
) -> Dict[str, List[str]]:
    """Map alias strings (id, name, display_name, last id segment) -> real ids.

    Lightweight models often return short names instead of the dotted ids they
    were shown; this index maps them back. Scoped to ``ids`` (the leaves being
    clustered) to avoid matching unrelated components.
    """
    index: Dict[str, List[str]] = defaultdict(list)
    for cid in ids:
        node = components.get(cid)
        if not node:
            continue
        aliases = {cid}
        if node.name:
            aliases.add(node.name)
        if node.display_name:
            aliases.add(node.display_name)
        last = cid.rsplit(".", 1)[-1] if "." in cid else cid
        aliases.add(last)
        for alias in aliases:
            if alias:
                index[str(alias)].append(cid)
    return index


def _resolve_id(raw: str, index: Dict[str, List[str]]) -> str | None:
    """Resolve a single LLM-returned string to a real component id, or None."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    cands = index.get(raw)
    if cands:
        return cands[0]
    low = raw.lower()
    for alias, cids in index.items():
        if alias.lower() == low:
            return cids[0]
    return None


def _resolve_module_components(
    module_tree: Dict[str, Any],
    components: Dict[str, Node],
    scope_ids: List[str] | None = None,
) -> None:
    """In-place: resolve LLM-returned component strings to real component ids.

    Tolerates the LLM returning short names / display_names instead of the
    dotted ids it was given. Scoped to ``scope_ids`` (the leaves being
    clustered) when provided, else all components. Unresolvable entries are
    dropped with a warning; the module's ``components`` list is replaced with
    the resolved ids so downstream consumers receive valid ids.
    """
    ids = scope_ids if scope_ids is not None else list(components.keys())
    index = _build_name_index(ids, components)
    for module_name, module_info in module_tree.items():
        raw_list = module_info.get("components", []) or []
        resolved: List[str] = []
        seen: set[str] = set()
        for raw in raw_list:
            if not isinstance(raw, str) or not raw.strip():
                continue
            rid = _resolve_id(raw, index)
            if rid and rid not in seen:
                seen.add(rid)
                resolved.append(rid)
            else:
                logger.warning(
                    "Skipping unresolvable component '%s' in module '%s'",
                    raw.strip(),
                    module_name,
                )
        module_info["components"] = resolved


def parse_llm_response(response: str) -> Dict[str, Any]:
    """Parse LLM response to extract grouped components (tolerant parser).

    Accepts, in order of preference:
      - JSON wrapped in <GROUPED_COMPONENTS>...</GROUPED_COMPONENTS> tags
      - JSON inside a ```json ...``` / ``` ... ``` code fence
      - A bare JSON object anywhere in the response

    qwen3-style <think>...</think> reasoning blocks are stripped first.
    """
    if not response or not response.strip():
        raise ValueError("Empty LLM response")

    cleaned = _strip_thinking(response)

    candidates: List[str] = []
    if "<GROUPED_COMPONENTS>" in cleaned and "</GROUPED_COMPONENTS>" in cleaned:
        candidates.append(
            cleaned.split("<GROUPED_COMPONENTS>")[1].split("</GROUPED_COMPONENTS>")[0]
        )
    fence_match = _FENCE_PATTERN.search(cleaned)
    if fence_match:
        candidates.append(fence_match.group(1))
    try:
        candidates.append(_extract_json_object(cleaned))
    except ValueError:
        pass

    if not candidates:
        preview = (response or "")[:500]
        raise ValueError(
            "No JSON found in LLM response (no tags, code fence, or '{'). "
            f"Response preview: {preview!r}"
        )

    last_error: Exception | None = None
    for raw in candidates:
        content = raw.strip()
        if not content:
            continue
        try:
            module_tree = json.loads(content)
        except json.JSONDecodeError as e:
            last_error = e
            continue
        if not isinstance(module_tree, dict):
            last_error = ValueError(f"Expected dict, got {type(module_tree)}")
            continue
        return module_tree

    preview = (response or "")[:500]
    raise ValueError(
        f"Could not parse JSON from LLM response (last error: {last_error}). "
        f"Response preview: {preview!r}"
    )


def _should_disable_thinking(config: Config) -> bool:
    """Resolve the disable_thinking option, auto-detecting qwen3 when unset."""
    if config.disable_thinking is not None:
        return config.disable_thinking
    model = (config.cluster_model or config.main_model or "").lower()
    return "qwen3" in model


def _thinking_extra_body() -> dict[str, Any]:
    """Provider-specific params to disable thinking (Ollama qwen3)."""
    return {
        "reasoning_effort": "none",
        "chat_template_kwargs": {"enable_thinking": False},
    }


def call_llm_with_retry(
    potential_core_components: str,
    config: Config,
    module_tree: dict[str, Any] | None = None,
    module_name: str | None = None,
    max_retries: int = 3,
) -> Tuple[str, Dict[str, Any]]:
    """Call LLM with progressive retry strategies and tolerant parsing.

    Attempts:
      1. Pure-JSON prompt + json_object response_format + thinking disabled, temp 0.0
      2. Same as #1 with temperature 0.1
      3. Tags-based prompt without json mode (most compatible), temp 0.0
    """
    disable_thinking = _should_disable_thinking(config)
    json_mode = bool(getattr(config, "cluster_json_mode", True))
    extra_body = _thinking_extra_body() if disable_thinking else None
    json_response_format: dict[str, Any] | None = (
        {"type": "json_object"} if json_mode else None
    )

    sys_json, user_json = format_cluster_prompt(
        potential_core_components, module_tree, module_name,
        disable_thinking=disable_thinking, use_tags=False,
    )
    sys_tags, user_tags = format_cluster_prompt(
        potential_core_components, module_tree, module_name,
        disable_thinking=disable_thinking, use_tags=True,
    )

    # (system, user, response_format, extra_body, temperature)
    attempts: List[Tuple[str, str, dict[str, Any] | None, dict[str, Any] | None, float]] = [
        (sys_json, user_json, json_response_format, extra_body, 0.0),
        (sys_json, user_json, json_response_format, extra_body, 0.1),
        (sys_tags, user_tags, None, None, 0.0),
    ]

    last_error: Exception | None = None
    last_response = ""

    for idx, (system, user, rf, eb, temp) in enumerate(attempts[:max_retries]):
        try:
            last_response, _ = call_llm(
                user, config,
                model=config.cluster_model,
                temperature=temp,
                system=system,
                response_format=rf,
                extra_body=eb,
            )
            module_tree_result = parse_llm_response(last_response)
            return last_response, module_tree_result
        except Exception as e:
            last_error = e
            logger.warning(
                f"Attempt {idx + 1} failed: {e}. Response preview: "
                f"{last_response[:200] if last_response else 'N/A'}"
            )
            continue

    raise ValueError(f"Failed after {min(max_retries, len(attempts))} attempts: {last_error}")


def _heuristic_fallback(
    component_ids: List[str], components: Dict[str, Node], batch_idx: int
) -> Dict[str, Any]:
    """Group components by parent directory when LLM clustering fails.

    More useful than a single ``batch_N`` bucket: modules are named after the
    directory holding the components. Names are made unique across batches via
    a ``_b{idx}`` suffix.
    """
    by_dir: Dict[str, List[str]] = defaultdict(list)
    for cid in component_ids:
        node = components.get(cid)
        if node is None:
            continue
        rel = node.relative_path or "."
        parent = rel.rsplit("/", 1)[0] if "/" in rel else "."
        by_dir[parent].append(cid)

    if not by_dir:
        return {
            f"batch_{batch_idx + 1}": {"path": ".", "components": list(component_ids)}
        }

    result: Dict[str, Any] = {}
    used_names: set[str] = set()
    for dir_path, comps in by_dir.items():
        base = dir_path.replace("/", "_") or "root"
        candidate = f"{base}_b{batch_idx + 1}"
        n = 2
        while candidate in used_names:
            candidate = f"{base}_b{batch_idx + 1}_{n}"
            n += 1
        used_names.add(candidate)
        result[candidate] = {"path": dir_path, "components": comps}
    return result


def _cluster_one_batch(
    idx: int,
    batch: List[str],
    components: Dict[str, Node],
    config: Config,
) -> Dict[str, Any]:
    """Process a single batch. Returns module_tree or a heuristic fallback dict."""
    potential = format_potential_core_components(
        batch, components, include_code=False
    )
    try:
        _, module_tree = call_llm_with_retry(potential, config)
        logger.info(f"Batch {idx + 1} completed: {len(module_tree)} modules")
        return module_tree
    except Exception as e:
        logger.error(
            f"Batch {idx + 1} failed: {e}; using heuristic fallback by directory"
        )
        return _heuristic_fallback(batch, components, idx)


def cluster_components_batch(
    components_to_cluster: List[str],
    components: Dict[str, Node],
    config: Config,
    batch_size: int | None = None,
) -> Dict[str, Any]:
    """Cluster a list of components using batched LLM calls.

    Batches run sequentially when ``config.cluster_max_workers <= 1`` (local
    single-inference setups); otherwise they run in parallel.
    """
    if not components_to_cluster:
        return {}

    if batch_size is None:
        batch_size = int(getattr(config, "cluster_batch_size", MAX_COMPONENTS_PER_BATCH))
    total = len(components_to_cluster)
    logger.info(f"Batching {total} components into groups of {batch_size}")

    # Split into batches
    batches = [
        components_to_cluster[i : i + batch_size]
        for i in range(0, total, batch_size)
    ]

    num_batches = len(batches)
    workers = max(1, min(int(getattr(config, "cluster_max_workers", 1)), num_batches))
    batch_results: List[Dict[str, Any]] = [{}] * num_batches  # placeholder

    if workers <= 1:
        logger.info(f"Processing {num_batches} batch(es) sequentially")
        for idx, batch in enumerate(batches):
            batch_results[idx] = _cluster_one_batch(idx, batch, components, config)
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
                    batch_results[idx] = _heuristic_fallback(batches[idx], components, idx)

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

    batch_size = int(getattr(config, "cluster_batch_size", MAX_COMPONENTS_PER_BATCH))

    # If too many leaf nodes, use batch clustering
    if len(leaf_nodes) > batch_size:
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
    """Handle clustering for large sets (> cluster_batch_size)."""
    batch_size = int(getattr(config, "cluster_batch_size", MAX_COMPONENTS_PER_BATCH))
    logger.info(
        f"Large module detected ({len(leaf_nodes)} components), using batch clustering"
    )

    valid_leaf_nodes = [n for n in leaf_nodes if n in components]
    module_tree = cluster_components_batch(
        valid_leaf_nodes, components, config, batch_size=batch_size
    )

    if not module_tree:
        logger.warning("Batch clustering returned empty result")
        return {}

    # Map LLM-returned names back to real component ids (in place).
    _resolve_module_components(module_tree, components, scope_ids=valid_leaf_nodes)

    if not current_module_tree:
        current_module_tree.update(module_tree)

    # Recursively cluster each module's components
    for module_name, module_info in list(module_tree.items()):
        sub_leaf = [n for n in module_info.get("components", []) if n in components]

        if len(sub_leaf) > batch_size:
            module_info["children"] = cluster_modules(
                sub_leaf, components, config,
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
    """Handle clustering for smaller sets (<= cluster_batch_size)."""
    potential = format_potential_core_components(leaf_nodes, components, include_code=False)
    potential_with_code = format_potential_core_components(leaf_nodes, components, include_code=True)
    token_count = count_tokens(potential_with_code)

    # Skip clustering for small content
    if token_count <= MAX_TOKEN_PER_MODULE and len(leaf_nodes) <= SKIP_CLUSTER_MAX_LEAVES:
        return _build_simple_module_tree(
            leaf_nodes, components, current_module_tree, current_module_name
        )

    # Call LLM for clustering
    module_tree = _call_clustering_llm(
        potential, config, current_module_tree, current_module_name
    )
    if not module_tree:
        return {}

    return _process_clustering_results(
        module_tree, components, config,
        current_module_tree, current_module_path, scope_ids=leaf_nodes
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
    potential_core_components: str,
    config: Config,
    current_module_tree: dict[str, Any],
    current_module_name: str | None,
) -> Dict[str, Any] | None:
    """Call LLM for clustering with retry logic."""
    response = ""
    try:
        response, module_tree = call_llm_with_retry(
            potential_core_components, config, current_module_tree, current_module_name
        )
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
    scope_ids: List[str] | None = None,
) -> Dict[str, Any]:
    """Process clustering results and recurse into sub-modules."""
    # Map LLM-returned names back to real component ids (in place).
    _resolve_module_components(module_tree, components, scope_ids)

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
        sub_leaf = [n for n in module_info.get("components", []) if n in components]
        module_info["children"] = cluster_modules(
            sub_leaf, components, config,
            current_module_tree, module_name, current_module_path + [module_name]
        )

    return module_tree
