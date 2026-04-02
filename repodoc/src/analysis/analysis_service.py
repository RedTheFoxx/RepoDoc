"""
Analysis service: local repo structure + call graph (no GitHub clone).
"""

import logging
from typing import Any, Dict, List, Optional

from src.analysis.repo_analyzer import RepoAnalyzer
from src.analysis.call_graph_analyzer import CallGraphAnalyzer


logger = logging.getLogger(__name__)

# Supported languages for analysis
SUPPORTED_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "java",
    "csharp",
    "c",
    "cpp",
    "php",
    "go",
    "rust",
}


class AnalysisService:
    """Local repository analysis: structure + multi-language call graph."""

    def __init__(self) -> None:
        self.call_graph_analyzer = CallGraphAnalyzer()

    def _analyze_structure(
        self,
        repo_dir: str,
        include_patterns: Optional[List[str]],
        exclude_patterns: Optional[List[str]],
    ) -> Dict[str, Any]:
        repo_analyzer = RepoAnalyzer(include_patterns, exclude_patterns)
        return repo_analyzer.analyze_repository_structure(repo_dir)

    def _analyze_call_graph(
        self, file_tree: Dict[str, Any], repo_dir: str
    ) -> Dict[str, Any]:
        code_files = self.call_graph_analyzer.extract_code_files(file_tree)
        supported = self._filter_supported_languages(code_files)
        result = self.call_graph_analyzer.analyze_code_files(supported, repo_dir)
        result["call_graph"]["supported_languages"] = self._get_supported_languages()
        result["call_graph"]["unsupported_files"] = len(code_files) - len(supported)
        return result

    def _filter_supported_languages(self, code_files: List[Dict]) -> List[Dict]:
        return [f for f in code_files if f.get("language") in SUPPORTED_LANGUAGES]

    def _get_supported_languages(self) -> List[str]:
        return list(SUPPORTED_LANGUAGES)
