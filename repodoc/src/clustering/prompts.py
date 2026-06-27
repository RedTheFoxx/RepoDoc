"""Prompts for clustering components into modules.

``format_cluster_prompt`` returns a ``(system, user)`` tuple so that format
instructions live in the system message (followed more reliably by lightweight
models) while the data to process lives in the user message. The user message
is prefixed with ``/no_think`` when thinking is disabled (qwen3).
"""

from typing import Any

_SYSTEM_JSON = """\
You are a code analysis assistant. Group the provided software components into logical modules.

Output rules (STRICT):
- Output ONLY a JSON object. No prose, no markdown, no code fences, no explanations.
- The JSON is a dictionary mapping module name -> {"path": "<relative dir>", "components": ["comp1", "comp2"]}.
- Group semantically related components together (e.g. http, database, auth, utils).
- Include EVERY provided component exactly once. Do not drop, rename or invent any.
- Use short, descriptive module names (snake_case).

Example:
{"http": {"path": "src/http", "components": ["HttpRequest", "HttpResponse"]},
 "db": {"path": "src/db", "components": ["Model", "QuerySet"]}}

Return ONLY the JSON object.
""".strip()

_SYSTEM_TAGS = """\
You are a code analysis assistant. Group the provided software components into logical modules.

Output rules (STRICT):
- Output ONLY JSON wrapped between <GROUPED_COMPONENTS> and </GROUPED_COMPONENTS> tags.
- No prose outside the tags, no markdown, no explanations.
- The JSON is a dictionary mapping module name -> {"path": "<relative dir>", "components": ["comp1", "comp2"]}.
- Group semantically related components together.
- Include EVERY provided component exactly once. Do not drop, rename or invent any.

Example:
<GROUPED_COMPONENTS>
{"http": {"path": "src/http", "components": ["HttpRequest", "HttpResponse"]},
 "db": {"path": "src/db", "components": ["Model", "QuerySet"]}}
</GROUPED_COMPONENTS>

Return ONLY the tagged JSON.
""".strip()


def _format_tree(
    tree: dict[str, Any], module_name: str | None, indent: int = 0
) -> list[str]:
    lines: list[str] = []
    for key, value in tree.items():
        label = f"{key} (current module)" if key == module_name else key
        lines.append(f"{'  ' * indent}{label}")
        comps = value.get("components", [])
        lines.append(f"{'  ' * (indent + 1)}Core components: {', '.join(comps)}")
        children = value.get("children")
        if isinstance(children, dict) and children:
            lines.append(f"{'  ' * (indent + 1)}Children:")
            lines.extend(_format_tree(children, module_name, indent + 2))
    return lines


def format_cluster_prompt(
    potential_core_components: str,
    module_tree: dict[str, Any] | None = None,
    module_name: str | None = None,
    disable_thinking: bool = False,
    use_tags: bool = False,
) -> tuple[str, str]:
    """Build the cluster prompt as a ``(system, user)`` tuple.

    Args:
        potential_core_components: Formatted component list to group.
        module_tree: Existing module structure (module-level clustering). Repo-level
            when empty/None.
        module_name: Name of the module currently being refined (module-level only).
        disable_thinking: Prefix the user message with ``/no_think`` (qwen3).
        use_tags: Ask for JSON wrapped in ``<GROUPED_COMPONENTS>`` tags instead of
            pure JSON (used as a fallback retry strategy).
    """
    module_tree = module_tree or {}
    system = _SYSTEM_TAGS if use_tags else _SYSTEM_JSON

    user_lines: list[str] = []
    if disable_thinking:
        user_lines.append("/no_think")
        user_lines.append("")

    if module_tree:
        user_lines.append("Existing module structure:")
        user_lines.append("<MODULE_TREE>")
        user_lines.extend(_format_tree(module_tree, module_name, 0))
        user_lines.append("</MODULE_TREE>")
        user_lines.append("")
        user_lines.append(f"Components to group (in module {module_name or ''}):")
    else:
        user_lines.append("Components to group into modules:")

    user_lines.append("<POTENTIAL_CORE_COMPONENTS>")
    user_lines.append(potential_core_components)
    user_lines.append("</POTENTIAL_CORE_COMPONENTS>")
    user_lines.append("")
    user_lines.append("Return ONLY the JSON object.")

    return system, "\n".join(user_lines)
