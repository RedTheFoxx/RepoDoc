"""Prompts for clustering components into modules."""

from typing import Any

CLUSTER_REPO_PROMPT = """
You are a code analysis assistant. Your task is to group software components into logical modules.

## Rules (STRICTLY FOLLOW):
1. ONLY output the JSON structure inside <GROUPED_COMPONENTS> tags - NO explanation, NO introduction, NO markdown formatting
2. The JSON must be a dictionary with module names as keys
3. Each module must have exactly: "path" (string) and "components" (list of strings)
4. Group components that are semantically related (e.g., all HTTP-related components together, all database-related together)
5. Include all provided components - do not exclude any unless clearly unrelated
6. Use descriptive module names that reflect the functionality

## Component list:
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

## Output format (use this EXACT structure):
<GROUPED_COMPONENTS>
{{
    "http": {{
        "path": "django/http",
        "components": ["HttpRequest", "HttpResponse", "JsonResponse"]
    }},
    "database": {{
        "path": "django/db",
        "components": ["Model", "QuerySet", "Transaction"]
    }}
}}
</GROUPED_COMPONENTS>

## CRITICAL:
- Output ONLY the content between <GROUPED_COMPONENTS> and </GROUPED_COMPONENTS>
- Do NOT include any other text, explanations, or markdown
- The JSON must be valid and parseable
""".strip()

CLUSTER_MODULE_PROMPT = """
You are a code analysis assistant. Your task is to group software components into logical sub-modules.

## Existing module structure:
<MODULE_TREE>
{module_tree}
</MODULE_TREE>

## Components to group (in module {module_name}):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

## Rules (STRICTLY FOLLOW):
1. ONLY output the JSON structure inside <GROUPED_COMPONENTS> tags - NO explanation, NO introduction, NO markdown
2. Group components that are semantically related within this module
3. Use descriptive sub-module names that reflect the functionality
4. Include all provided components

## Output format:
<GROUPED_COMPONENTS>
{{
    "submodule_name": {{
        "path": "relative/path",
        "components": ["comp1", "comp2"]
    }}
}}
</GROUPED_COMPONENTS>

## CRITICAL: Output ONLY the JSON between the tags, nothing else.
""".strip()


def format_cluster_prompt(
    potential_core_components: str,
    module_tree: dict[str, Any] | None = None,
    module_name: str | None = None,
) -> str:
    """Build cluster prompt: repo-level or module-level."""
    module_tree = module_tree or {}
    lines: list[str] = []

    def _format_tree(tree: dict[str, Any], indent: int = 0) -> None:
        for key, value in tree.items():
            if key == module_name:
                lines.append(f"{'  ' * indent}{key} (current module)")
            else:
                lines.append(f"{'  ' * indent}{key}")
            comps = value.get("components", [])
            lines.append(f"{'  ' * (indent + 1)} Core components: {', '.join(comps)}")
            children = value.get("children")
            if isinstance(children, dict) and children:
                lines.append(f"{'  ' * (indent + 1)} Children:")
                _format_tree(children, indent + 2)

    _format_tree(module_tree, 0)
    formatted_module_tree = "\n".join(lines)

    if not module_tree:
        return CLUSTER_REPO_PROMPT.format(
            potential_core_components=potential_core_components
        )
    return CLUSTER_MODULE_PROMPT.format(
        potential_core_components=potential_core_components,
        module_tree=formatted_module_tree,
        module_name=module_name or "",
    )
