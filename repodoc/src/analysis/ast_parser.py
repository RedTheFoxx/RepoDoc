"""
Parser: extract code components (Node dict) from repo via analysis service.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set

from src.analysis.analysis_service import AnalysisService
from src.analysis.models.core import Node

logger = logging.getLogger(__name__)


class DependencyParser:
    """Extract code components from multi-language repositories."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = os.path.abspath(repo_path)
        self.components: Dict[str, Node] = {}
        self.modules: Set[str] = set()
        self.analysis_service = AnalysisService()

    def parse_repository(
        self, filtered_folders: Optional[List[str]] = None
    ) -> Dict[str, Node]:
        structure_result = self.analysis_service._analyze_structure(
            self.repo_path, include_patterns=None, exclude_patterns=None
        )
        call_graph_result = self.analysis_service._analyze_call_graph(
            structure_result["file_tree"], self.repo_path
        )
        self._build_components_from_analysis(call_graph_result)
        logger.debug(
            "Found %d components across %d modules",
            len(self.components),
            len(self.modules),
        )
        return self.components

    def _build_components_from_analysis(self, call_graph_result: Dict) -> None:
        functions = call_graph_result.get("functions", [])
        relationships = call_graph_result.get("relationships", [])
        component_id_mapping: Dict[str, str] = {}

        for func_dict in functions:
            component_id = func_dict.get("id", "")
            if not component_id:
                continue
            node = Node(
                id=component_id,
                name=func_dict.get("name", ""),
                component_type=func_dict.get(
                    "component_type", func_dict.get("node_type", "function")
                ),
                file_path=func_dict.get("file_path", ""),
                relative_path=func_dict.get("relative_path", ""),
                source_code=func_dict.get(
                    "source_code", func_dict.get("code_snippet", "")
                ),
                start_line=func_dict.get("start_line", 0),
                end_line=func_dict.get("end_line", 0),
                has_docstring=bool(func_dict.get("docstring")),
                docstring=func_dict.get("docstring") or "",
                parameters=func_dict.get("parameters"),
                node_type=func_dict.get("node_type", "function"),
                base_classes=func_dict.get("base_classes"),
                class_name=func_dict.get("class_name"),
                display_name=func_dict.get("display_name", ""),
                component_id=component_id,
            )
            self.components[component_id] = node
            component_id_mapping[component_id] = component_id
            legacy_id = f"{func_dict.get('file_path', '')}:{func_dict.get('name', '')}"
            if legacy_id and legacy_id != component_id:
                component_id_mapping[legacy_id] = component_id
            if "." in component_id:
                module_path = ".".join(component_id.split(".")[:-1])
                if module_path:
                    self.modules.add(module_path)

        for rel_dict in relationships:
            caller_id = component_id_mapping.get(rel_dict.get("caller", ""))
            callee_id = component_id_mapping.get(rel_dict.get("callee", ""))
            if not callee_id:
                for comp_id, comp_node in self.components.items():
                    if comp_node.name == rel_dict.get("callee", ""):
                        callee_id = comp_id
                        break
            if caller_id and caller_id in self.components and callee_id:
                self.components[caller_id].depends_on.add(callee_id)

    def save_dependency_graph(self, output_path: str) -> Dict:
        result = {}
        for cid, component in self.components.items():
            d = component.model_dump()
            if isinstance(d.get("depends_on"), set):
                d["depends_on"] = list(d["depends_on"])
            result[cid] = d
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return result
