# Imports below run after sys.path setup; order is intentional.
# ruff: noqa: E402

import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add repodoc parent to path for internal "src" imports
# This works both in development and in hatch-built package
_current = Path(__file__).resolve()
# Try different parent levels
for parent in [_current.parent.parent.parent, _current.parent.parent, _current.parent]:
    if (parent / "src").exists() and str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
        break

import click
import logging

from dotenv import load_dotenv

load_dotenv()

from src.config import Config
from src.analysis import DependencyGraphBuilder
from src.clustering import cluster_modules
from pipeline import run_pipeline
from src.utils import file_manager


def _quiet_http_logging(verbose: bool) -> None:
    """Silence noisy HTTP 200-OK logs from the OpenAI/httpx client unless verbose."""
    level = logging.DEBUG if verbose else logging.WARNING
    for name in ("httpx", "httpcore", "openai", "openai._base_client"):
        logging.getLogger(name).setLevel(level)


def make_config(
    repo_path: str,
    output_dir: str = "output",
    llm_concept_extraction: bool = False,
    llm_concept_max_components: int = 100,
) -> Config:
    return Config(
        repo_path=repo_path,
        output_dir=output_dir,
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        llm_api_key=os.getenv("LLM_API_KEY", "sk-1234"),
        main_model=os.getenv("MAIN_MODEL", "deepseek-chat"),
        cluster_model=os.getenv("CLUSTER_MODEL")
        or os.getenv("MAIN_MODEL", "deepseek-chat"),
        llm_concept_extraction=llm_concept_extraction,
        llm_concept_max_components=llm_concept_max_components,
    )


def get_project_name(repo_path: str) -> str:
    """Extract safe project name from repo path."""
    repo_name = os.path.basename(os.path.normpath(repo_path))
    return "".join(c if c.isalnum() else "_" for c in repo_name)


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """RepoDoc: Automated documentation via Repository Knowledge Graph."""
    pass


@cli.command(short_help="Analyze repository dependencies")
@click.argument("repo_path", default=".")
@click.option("-o", "--output-dir", default="output", help="Output directory")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
def analyze(repo_path: str, output_dir: str, verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    _quiet_http_logging(verbose)
    config = make_config(repo_path, output_dir)
    builder = DependencyGraphBuilder(config)
    try:
        components, leaf_nodes = builder.build_dependency_graph()
        click.echo(f"Components: {len(components)}")
        click.echo(f"Leaf nodes: {len(leaf_nodes)}")
        click.echo(f"Dependency graph saved: {config.dependency_graph_dir}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command(short_help="Cluster components into hierarchical modules")
@click.argument("repo_path", default=".")
@click.option("-o", "--output-dir", default="output", help="Output directory")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
def cluster(repo_path: str, output_dir: str, verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    _quiet_http_logging(verbose)
    config = make_config(repo_path, output_dir)
    project_name = get_project_name(repo_path)
    data_dir = os.path.join(output_dir, "data")
    builder = DependencyGraphBuilder(config)
    try:
        components, leaf_nodes = builder.build_dependency_graph()
        click.echo(f"Components: {len(components)}")
        click.echo(f"Leaf nodes: {len(leaf_nodes)}")
        file_manager.ensure_directory(data_dir)
        module_tree = cluster_modules(leaf_nodes, components, config)
        first_path = os.path.join(data_dir, f"{project_name}_module_tree.json")
        tree_path = os.path.join(data_dir, f"{project_name}_module_tree.json")
        file_manager.save_json(module_tree, first_path)
        file_manager.save_json(module_tree, tree_path)
        click.echo(f"Clustering done: {len(module_tree)} top-level module(s)")
        click.echo(f"Saved: {first_path}, {tree_path}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command(short_help="Generate documentation using AI agents")
@click.argument("repo_path", default=".")
@click.option("-o", "--output-dir", default="output", help="Output directory")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.option(
    "--llm-concept-extraction",
    is_flag=True,
    help="Enable LLM-enhanced concept extraction (higher quality but more token usage)",
)
@click.option(
    "--llm-concept-max-components",
    default=100,
    help="Max components to process with LLM for concept extraction (default: 100)",
)
def docs(
    repo_path: str,
    output_dir: str,
    verbose: bool,
    llm_concept_extraction: bool,
    llm_concept_max_components: int,
):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    _quiet_http_logging(verbose)
    config = make_config(
        repo_path,
        output_dir,
        llm_concept_extraction=llm_concept_extraction,
        llm_concept_max_components=llm_concept_max_components,
    )
    project_name = get_project_name(repo_path)
    data_dir = os.path.join(output_dir, "data")
    try:
        tree_path = os.path.join(data_dir, f"{project_name}_module_tree.json")
        if not os.path.exists(tree_path):
            click.echo("module_tree.json not found. Running clustering first...")
            click.echo("=" * 40)
            click.echo("Phase 1: Analyzing dependencies...")
            builder = DependencyGraphBuilder(config)
            components, leaf_nodes = builder.build_dependency_graph()
            click.echo(f"  Components: {len(components)}")
            click.echo(f"  Leaf nodes: {len(leaf_nodes)}")

            click.echo("=" * 40)
            click.echo("Phase 2: Clustering modules...")
            file_manager.ensure_directory(data_dir)
            module_tree = cluster_modules(leaf_nodes, components, config)
            file_manager.save_json(module_tree, tree_path)
            click.echo(f"  Modules: {len(module_tree)}")
            click.echo("=" * 40)

        results = run_pipeline(config, generate_docs=True)
        click.echo(f"Documentation generated: {results['docs_directory']}")
        click.echo(f"Total components: {results['total_components']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command(short_help="Run all phases: analyze -> cluster -> docs")
@click.argument("repo_path", default=".")
@click.option("-o", "--output-dir", default="output", help="Output directory")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.option(
    "--llm-concept-extraction",
    is_flag=True,
    help="Enable LLM-enhanced concept extraction (higher quality but more token usage)",
)
@click.option(
    "--llm-concept-max-components",
    default=100,
    help="Max components to process with LLM for concept extraction (default: 100)",
)
def generate(
    repo_path: str,
    output_dir: str,
    verbose: bool,
    llm_concept_extraction: bool,
    llm_concept_max_components: int,
):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    _quiet_http_logging(verbose)
    config = make_config(
        repo_path,
        output_dir,
        llm_concept_extraction=llm_concept_extraction,
        llm_concept_max_components=llm_concept_max_components,
    )
    project_name = get_project_name(repo_path)
    data_dir = os.path.join(output_dir, "data")
    try:
        click.echo("=" * 40)
        click.echo("Phase 1: Analyzing dependencies...")
        builder = DependencyGraphBuilder(config)
        components, leaf_nodes = builder.build_dependency_graph()
        click.echo(f"  Components: {len(components)}")
        click.echo(f"  Leaf nodes: {len(leaf_nodes)}")

        click.echo("=" * 40)
        click.echo("Phase 2: Clustering modules...")
        file_manager.ensure_directory(data_dir)
        module_tree = cluster_modules(leaf_nodes, components, config)
        tree_path = os.path.join(data_dir, f"{project_name}_module_tree.json")
        file_manager.save_json(module_tree, tree_path)
        click.echo(f"  Modules: {len(module_tree)}")

        click.echo("=" * 40)
        click.echo("Phase 3: Generating documentation...")
        results = run_pipeline(config, generate_docs=True)

        click.echo("=" * 40)
        click.echo(f"Done! Documentation: {results['docs_directory']}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.group()
def config():
    """Manage RepoDoc configuration."""
    pass


@config.command("show")
def config_show():
    """Show current configuration."""
    click.echo("Current RepoDoc Configuration:")
    click.echo("-" * 40)

    config_data = {
        "LLM Base URL": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        "LLM API Key": (
            "***" + os.getenv("LLM_API_KEY", "")[-4:]
            if os.getenv("LLM_API_KEY")
            else "not set"
        ),
        "Main Model": os.getenv("MAIN_MODEL", "deepseek-chat"),
        "Cluster Model": os.getenv(
            "CLUSTER_MODEL", os.getenv("MAIN_MODEL", "deepseek-chat")
        ),
    }

    for key, value in config_data.items():
        click.echo(f"  {key}: {value}")


VALID_CONFIG_KEYS = ["LLM_BASE_URL", "LLM_API_KEY", "MAIN_MODEL", "CLUSTER_MODEL"]


@config.command("set", short_help="Set a config value in .env")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value in the project .env file.

    Valid keys:

    \b
      LLM_BASE_URL (LLM API base URL)
      LLM_API_KEY (API key)
      MAIN_MODEL (model for documentation)
      CLUSTER_MODEL (model for clustering, defaults to MAIN_MODEL)

    Examples:

    \b
      repodoc config set MAIN_MODEL deepseek-chat
      repodoc config set LLM_BASE_URL http://localhost:4000/
      repodoc config set LLM_API_KEY sk-your-api-key
    """
    key_upper = key.upper()
    if key_upper not in VALID_CONFIG_KEYS:
        click.echo(f"Error: Invalid key '{key}'. Valid keys are:")
        for k in VALID_CONFIG_KEYS:
            click.echo(f"  - {k}")
        raise click.Abort()

    env_path = Path(".env")
    env_vars = {}

    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k] = v

    env_vars[key_upper] = value

    with open(env_path, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")

    click.echo(f"Set {key_upper}={value} in .env")


@config.command("validate")
def config_validate():
    """Validate configuration."""
    click.echo("Validating configuration...")

    errors = []
    warnings = []

    if not os.getenv("LLM_API_KEY"):
        errors.append("LLM_API_KEY is not set")

    if not os.getenv("LLM_BASE_URL"):
        warnings.append("LLM_BASE_URL not set, using default")

    if errors:
        click.echo("Errors:", err=True)
        for e in errors:
            click.echo(f"  - {e}", err=True)
    else:
        click.echo("Configuration is valid!")

    if warnings:
        click.echo("Warnings:")
        for w in warnings:
            click.echo(f"  - {w}")


@cli.command()
@click.argument("repo_path", default=".")
@click.argument("changed_files", nargs=-1, required=False)
@click.option("-o", "--output-dir", default="output", help="Output directory")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.option(
    "--base-commit",
    default=None,
    help="Base commit to compare against (auto-detect from metadata if not provided)",
)
@click.option(
    "--analyze-changes/--no-analyze-changes",
    default=True,
    help="Analyze changes to filter unimportant ones (default: enabled)",
)
@click.option(
    "--include-tests",
    is_flag=True,
    help="Include test files in analysis (default: exclude test files)",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt and automatically proceed",
)
def update(
    repo_path: str,
    changed_files: tuple,
    output_dir: str,
    verbose: bool,
    base_commit: str,
    analyze_changes: bool,
    include_tests: bool,
    yes: bool,
):
    """Update documentation incrementally for changed files.

    REPO_PATH: Path to the repository (default: current directory)
    CHANGED_FILES: List of changed files (optional, auto-detects via git if not provided)

    Example:
        repodoc update /path/to/flask src/flask/app.py src/flask/ctx.py
        repodoc update /path/to/flask --base-commit HEAD~1
        repodoc update /path/to/flask --analyze-changes
        repodoc update /path/to/flask --analyze-changes --include-tests
    """
    from src.graph import HeterogeneousGraph
    from src.incremental.incremental_updater import IncrementalUpdater
    from src.incremental.code_extractor import GitCodeExtractor
    from src.analysis.diff_analysis import (
        analyze_git_diff,
        filter_important_changes,
        ChangeType,
        ComponentChange,
    )
    import subprocess
    import time

    start_time = time.time()

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    _quiet_http_logging(verbose)

    config = make_config(repo_path, output_dir)
    project_name = get_project_name(repo_path)

    # Auto-detect base_commit from metadata if not provided
    metadata_path = os.path.join(output_dir, "data", f"{project_name}_metadata.json")
    stored_commit = None
    if os.path.exists(metadata_path):
        try:
            metadata = file_manager.load_json(metadata_path)
            stored_commit = metadata.get("generation_info", {}).get("git_commit")
            if stored_commit:
                click.echo(f"Found previous commit from metadata: {stored_commit[:8]}")
        except Exception:
            pass

    # Determine base_commit: user-provided > metadata > HEAD
    if not base_commit and stored_commit:
        base_commit = stored_commit
        click.echo(f"Using base commit: {base_commit[:8]}")

    # Get current HEAD commit
    current_commit = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        current_commit = result.stdout.strip()
        click.echo(f"Current commit: {current_commit[:8]}")
    except Exception as e:
        click.echo(f"Warning: Could not get current commit: {e}")

    # Analyze changes if requested
    analyses = None
    if analyze_changes and not changed_files:
        click.echo("\nAnalyzing git changes...")
        analyses = analyze_git_diff(repo_path, base_commit, include_tests)

        if not analyses:
            click.echo("No changes detected")
            return

        click.echo(f"\n{'=' * 60}")
        click.echo("CHANGE ANALYSIS RESULTS")
        click.echo(f"{'=' * 60}")

        important = filter_important_changes(analyses)

        for file_path, analysis in analyses.items():
            status = "✅ IMPORTANT" if analysis.has_important_changes else "❌ SKIP"
            click.echo(f"\n{status} {file_path}")
            for change in analysis.changes:
                click.echo(f"  - {change.change_type.value}: {change.name}")
                if change.details:
                    click.echo(f"    {change.details}")

        click.echo(f"\n{'=' * 60}")
        click.echo(
            f"Summary: {len(important)} important, {len(analyses) - len(important)} skipped"
        )

        if not important:
            click.echo(
                "\nNo important API changes detected. Documentation update not needed."
            )
            return

        changed_files = tuple(important.keys())
        click.echo(f"\nFiles with important changes: {list(changed_files)}")

    if not changed_files:
        click.echo("Detecting changed files via git...")
        try:
            if base_commit:
                result = subprocess.run(
                    ["git", "diff", "--name-only", base_commit],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            changed_files = tuple(result.stdout.strip().split("\n"))
            changed_files = [f for f in changed_files if f]
            click.echo(f"Found {len(changed_files)} changed files")
        except Exception as e:
            click.echo(f"Error detecting changes: {e}", err=True)
            return

    if not changed_files:
        click.echo("No changed files to process")
        return

    graph_path = os.path.join(
        output_dir, "data", f"{project_name}_knowledge_graph.json"
    )

    if not os.path.exists(graph_path):
        click.echo(f"Knowledge graph not found: {graph_path}")
        click.echo("Run 'repodoc all-phases' first to generate initial documentation")
        return

    click.echo(f"Loading knowledge graph from: {graph_path}")
    graph = HeterogeneousGraph.load(graph_path)
    click.echo(f"  Nodes: {graph.node_count()}")
    click.echo(f"  Edges: {graph.edge_count()}")

    # Load module_tree
    module_tree_path = os.path.join(
        output_dir, "data", f"{project_name}_module_tree.json"
    )
    module_tree = {}
    if os.path.exists(module_tree_path):
        module_tree = file_manager.load_json(module_tree_path) or {}
        click.echo(f"  Module tree: {len(module_tree)} modules")
    else:
        click.echo("  Module tree not found - will not filter by module_tree")

    updater = IncrementalUpdater(graph, config)

    normalized_files = []
    for f in changed_files:
        if not f.startswith("/"):
            f = os.path.abspath(os.path.join(repo_path, f))
        normalized_files.append(f)

    click.echo(f"\nAnalyzing impact of {len(normalized_files)} changed files...")
    impact = updater.compute_impact_graph(normalized_files, module_tree)

    # Build change_map: component_id → ComponentChange
    # This maps component IDs from impact graph to their change information
    change_map: dict[str, ComponentChange] = {}

    # Check if we have analyses from earlier (if --analyze-changes was used)
    # If not, recompute them here
    analyses_to_use = None
    if "analyses" in dir() and analyses is not None:
        analyses_to_use = analyses
    else:
        # Need to recompute analyses for change mapping
        try:
            analyses_to_use = analyze_git_diff(repo_path, base_commit, include_tests)
        except Exception:
            pass

    if analyses_to_use:
        for file_path, analysis in analyses_to_use.items():
            for change in analysis.changes:
                if change.change_type in (
                    ChangeType.NEW_COMPONENT,
                    ChangeType.API_SIGNATURE_CHANGED,
                    ChangeType.REMOVED_COMPONENT,
                ):
                    # Match KG format: src/flask/globals.py -> src.flask.globals.FlaskProxy
                    module_path = change.file_path
                    for ext in [
                        ".py",
                        ".js",
                        ".jsx",
                        ".ts",
                        ".tsx",
                        ".java",
                        ".cs",
                        ".c",
                        ".cpp",
                        ".cc",
                        ".cxx",
                        ".h",
                        ".hpp",
                        ".php",
                    ]:
                        if module_path.endswith(ext):
                            module_path = module_path[: -len(ext)]
                            break
                    component_id = f"{module_path.replace('/', '.')}.{change.name}"
                    change_map[component_id] = change

    click.echo(f"\n{'=' * 60}")
    click.echo("IMPACT ANALYSIS RESULTS")
    click.echo(f"{'=' * 60}")
    click.echo(f"  Changed files: {len(impact['changed_files'])}")
    click.echo(f"  Changed components: {len(impact['changed_components'])}")
    click.echo(f"  Total affected (in module_tree): {impact['total_affected']}")

    # Show new components (not in knowledge graph)
    if impact.get("new_components"):
        click.echo("\n  New components (not in knowledge graph):")
        for comp in impact["new_components"][:10]:
            click.echo(f"    + {comp}")
        if len(impact["new_components"]) > 10:
            click.echo(f"    ... and {len(impact['new_components']) - 10} more")
        click.echo(
            "\n  ⚠️  These are new components. Run 'repodoc all-phases' to include them."
        )

    # Show components not in module_tree
    if impact.get("not_in_module_tree"):
        click.echo("\n  Components not in module_tree (skipped):")
        for comp in impact["not_in_module_tree"][:5]:
            click.echo(f"    - {comp}")
        if len(impact["not_in_module_tree"]) > 5:
            click.echo(f"    ... and {len(impact['not_in_module_tree']) - 5} more")

    if impact["changed_components"]:
        click.echo("\n  Changed components (in module_tree):")
        for comp in impact["changed_components"][:10]:
            click.echo(f"    - {comp}")
        if len(impact["changed_components"]) > 10:
            click.echo(f"    ... and {len(impact['changed_components']) - 10} more")

    if impact["total_affected"] == 0:
        click.echo("\nNo documentation updates needed")
        return

    click.echo(
        f"\nThis will update documentation for {impact['total_affected']} component(s)"
    )
    if not yes and not click.confirm("Do you want to continue?"):
        click.echo("Aborted")
        return

    click.echo("\nRegenerating documentation for affected components...")

    import asyncio
    from pipeline.generator import DocPipeline
    from src.analysis.models.core import Node

    pipeline = DocPipeline(config)
    pipeline.components = {}

    # Only load code nodes (not doc nodes)
    for node_id, attrs in graph.nodes(data=True):
        if attrs.get("node_type") == "code":
            data = attrs.get("data", {}).copy()
            # KG stores 'type' but Node model expects 'component_type'
            # Map 'type' to 'component_type' if needed
            if "component_type" not in data and "type" in data:
                data["component_type"] = data["type"]
            # Skip if neither component_type nor type is present (e.g., doc nodes)
            if "component_type" not in data:
                continue
            node = Node(**data)
            pipeline.components[node_id] = node

    pipeline.load_module_tree()
    pipeline.initialize_agent()

    docs_dir = config.docs_dir
    module_tree = pipeline.module_tree

    # Initialize GitCodeExtractor for extracting code at specific commits
    code_extractor = GitCodeExtractor(repo_path)

    async def regenerate_component(
        node_id: str, change_info: Optional[ComponentChange] = None
    ):
        node = pipeline.components.get(node_id)
        if not node:
            return None

        module_name = None
        for mod_name, mod_info in module_tree.items():
            if node_id in mod_info.get("components", []):
                module_name = mod_name
                break

        if not module_name:
            return None

        module_dir = os.path.join(docs_dir, module_name)
        file_manager.ensure_directory(module_dir)

        output_path = os.path.join(module_dir, f"{node.name}.md")

        # Determine source code based on change type
        source_code = node.source_code or ""
        docstring = node.docstring or ""
        parameters = node.parameters or []

        if change_info and current_commit:
            # Directly changed component - extract from current_commit
            if change_info.change_type in (
                ChangeType.NEW_COMPONENT,
                ChangeType.API_SIGNATURE_CHANGED,
            ):
                extracted = code_extractor.extract_component_at_commit(
                    change_info.file_path,
                    change_info.name,
                    current_commit,
                )
                if extracted:
                    source_code = extracted.get("source_code", source_code)
                    docstring = extracted.get("docstring", docstring)
                    parameters = extracted.get("parameters", parameters)

            elif change_info.change_type == ChangeType.REMOVED_COMPONENT:
                # Component was removed - add deprecation note
                docstring = f"⚠️ DEPRECATED: This component was removed.\n\n{docstring}"

        else:
            # Downstream component (not directly changed) - use current working tree
            if node.file_path:
                full_path = os.path.join(repo_path, node.file_path)
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            current_content = f.read()
                        source_code = current_content
                    except Exception:
                        pass

        component = {
            "name": node.name,
            "component_type": node.component_type,
            "file_path": node.file_path,
            "relative_path": node.relative_path,
            "docstring": docstring,
            "source_code": source_code or "",
            "depends_on": list(node.depends_on) if node.depends_on else [],
        }

        result = await pipeline.agent.execute(
            {
                "type": "write_doc",
                "config": config,
                "input": {
                    "type": "component",
                    "component": component,
                    "output_path": output_path,
                },
            }
        )
        return result

    async def run_regeneration():
        tasks = []
        for comp_id in impact["affected_components"]:
            change_info = change_map.get(comp_id)
            task = asyncio.create_task(regenerate_component(comp_id, change_info))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    results = asyncio.run(run_regeneration())

    def is_successful_result(r) -> bool:
        if isinstance(r, Exception):
            return False
        if not r:
            return False
        return getattr(r, "success", False)

    success_count = sum(1 for r in results if is_successful_result(r))
    click.echo(
        f"\nSuccessfully regenerated {success_count}/{len(results)} component(s)"
    )

    duration = time.time() - start_time

    token_history = []
    if pipeline.agent and hasattr(pipeline.agent, "tools"):
        llm_tool = pipeline.agent.tools.get("llm_caller")
        if llm_tool and hasattr(llm_tool, "get_token_usage_history"):
            token_history = llm_tool.get_token_usage_history()

    total_tokens = sum(u.get("total_tokens", 0) for u in token_history)
    prompt_tokens = sum(u.get("prompt_tokens", 0) for u in token_history)
    completion_tokens = sum(u.get("completion_tokens", 0) for u in token_history)
    llm_calls = len(token_history)

    from src.utils import log_operation

    log_operation(
        output_dir=output_dir,
        operation_type="incremental_update",
        repo_path=repo_path,
        git_commit=current_commit,
        base_commit=base_commit,
        duration_seconds=duration,
        total_tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        llm_calls=llm_calls,
        components_processed=len(impact["affected_components"]),
        components_updated=success_count,
        status="success",
    )

    # Update metadata with new commit
    if current_commit and os.path.exists(metadata_path):
        try:
            metadata = file_manager.load_json(metadata_path)
            if metadata:
                # Update git_commit to new HEAD
                metadata["generation_info"]["git_commit"] = current_commit
                # Add update info
                if "update_info" not in metadata:
                    metadata["update_info"] = {}
                metadata["update_info"]["last_update_commit"] = current_commit
                metadata["update_info"]["last_base_commit"] = base_commit
                metadata["update_info"]["components_updated"] = success_count
                metadata["update_info"]["affected_components"] = impact["affected_components"]
                metadata["generation_info"]["timestamp"] = datetime.now().isoformat()
                file_manager.save_json(metadata, metadata_path)
                click.echo(f"\nUpdated metadata with new commit: {current_commit[:8]}")
        except Exception as e:
            click.echo(f"Warning: Could not update metadata: {e}")

    click.echo("\nDocumentation update complete!")
    click.echo("Updated components:")
    for comp in impact["affected_components"][:10]:
        click.echo(f"  - {comp}")
    if len(impact["affected_components"]) > 10:
        click.echo(f"  ... and {len(impact['affected_components']) - 10} more")


if __name__ == "__main__":
    cli()
