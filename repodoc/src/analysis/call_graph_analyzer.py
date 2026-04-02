"""
Multi-language call graph analysis: routes to language analyzers and resolves relationships.
"""

import logging
import traceback
from pathlib import Path
from typing import Dict, List

from src.analysis.models.core import Node, CallRelationship
from src.analysis.utils.patterns import CODE_EXTENSIONS
from src.analysis.utils.security import safe_open_text

logger = logging.getLogger(__name__)


class CallGraphAnalyzer:
    def __init__(self) -> None:
        self.functions: Dict[str, Node] = {}
        self.call_relationships: List[CallRelationship] = []

    def analyze_code_files(self, code_files: List[Dict], base_dir: str) -> Dict:
        self.functions = {}
        self.call_relationships = []
        for file_info in code_files:
            self._analyze_code_file(base_dir, file_info)
        self._resolve_call_relationships()
        self._deduplicate_relationships()
        viz_data = self._generate_visualization_data()
        return {
            "call_graph": {
                "total_functions": len(self.functions),
                "total_calls": len(self.call_relationships),
                "languages_found": list({f.get("language") for f in code_files}),
                "files_analyzed": len(code_files),
            },
            "functions": [f.model_dump() for f in self.functions.values()],
            "relationships": [r.model_dump() for r in self.call_relationships],
            "visualization": viz_data,
        }

    def extract_code_files(self, file_tree: Dict) -> List[Dict]:
        code_files = []

        def traverse(tree: Dict) -> None:
            if tree.get("type") == "file":
                ext = tree.get("extension", "").lower()
                if ext in CODE_EXTENSIONS:
                    code_files.append(
                        {
                            "path": tree["path"],
                            "name": tree["name"],
                            "extension": ext,
                            "language": CODE_EXTENSIONS[ext],
                        }
                    )
            elif tree.get("type") == "directory" and tree.get("children"):
                for child in tree["children"]:
                    traverse(child)

        traverse(file_tree)
        return code_files

    def _analyze_code_file(self, repo_dir: str, file_info: Dict) -> None:
        base = Path(repo_dir)
        file_path = base / file_info["path"]
        try:
            content = safe_open_text(base, file_path)
            # Skip ANTLR-generated files which can cause recursion errors
            if "ANTLR GENERATED CODE" in content[:500]:
                logger.debug("Skipping ANTLR generated file: %s", file_path)
                return
            lang = file_info["language"]
            if lang == "python":
                self._analyze_python_file(str(file_path), content, repo_dir)
            elif lang == "javascript":
                self._analyze_javascript_file(str(file_path), content, repo_dir)
            elif lang == "typescript":
                self._analyze_typescript_file(str(file_path), content, repo_dir)
            elif lang == "java":
                self._analyze_java_file(str(file_path), content, repo_dir)
            elif lang == "csharp":
                self._analyze_csharp_file(str(file_path), content, repo_dir)
            elif lang == "c":
                self._analyze_c_file(str(file_path), content, repo_dir)
            elif lang == "cpp":
                self._analyze_cpp_file(str(file_path), content, repo_dir)
            elif lang == "php":
                self._analyze_php_file(str(file_path), content, repo_dir)
            elif lang == "go":
                self._analyze_go_file(str(file_path), content, repo_dir)
            elif lang == "rust":
                self._analyze_rust_file(str(file_path), content, repo_dir)
        except Exception as e:
            logger.error("Error analyzing %s: %s", file_path, e)
            logger.debug(traceback.format_exc())

    def _analyze_python_file(self, file_path: str, content: str, base_dir: str) -> None:
        from src.analysis.analyzers.python import analyze_python_file

        functions, relationships = analyze_python_file(
            file_path, content, repo_path=base_dir
        )
        for func in functions:
            fid = func.id or f"{file_path}:{func.name}"
            self.functions[fid] = func
        self.call_relationships.extend(relationships)

    def _analyze_javascript_file(
        self, file_path: str, content: str, repo_dir: str
    ) -> None:
        from src.analysis.analyzers.javascript import (
            analyze_javascript_file_treesitter,
        )

        functions, relationships = analyze_javascript_file_treesitter(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_typescript_file(
        self, file_path: str, content: str, repo_dir: str
    ) -> None:
        from src.analysis.analyzers.typescript import (
            analyze_typescript_file_treesitter,
        )

        functions, relationships = analyze_typescript_file_treesitter(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_c_file(self, file_path: str, content: str, repo_dir: str) -> None:
        from src.analysis.analyzers.c import analyze_c_file

        functions, relationships = analyze_c_file(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_cpp_file(self, file_path: str, content: str, repo_dir: str) -> None:
        from src.analysis.analyzers.cpp import analyze_cpp_file

        functions, relationships = analyze_cpp_file(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_java_file(self, file_path: str, content: str, repo_dir: str) -> None:
        from src.analysis.analyzers.java import analyze_java_file

        functions, relationships = analyze_java_file(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_csharp_file(self, file_path: str, content: str, repo_dir: str) -> None:
        from src.analysis.analyzers.csharp import analyze_csharp_file

        functions, relationships = analyze_csharp_file(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_php_file(self, file_path: str, content: str, repo_dir: str) -> None:
        from src.analysis.analyzers.php import analyze_php_file

        functions, relationships = analyze_php_file(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_go_file(self, file_path: str, content: str, repo_dir: str) -> None:
        from src.analysis.analyzers.go import analyze_go_file

        functions, relationships = analyze_go_file(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _analyze_rust_file(self, file_path: str, content: str, repo_dir: str) -> None:
        from src.analysis.analyzers.rust import analyze_rust_file

        functions, relationships = analyze_rust_file(
            file_path, content, repo_path=repo_dir
        )
        for func in functions:
            self.functions[func.id or f"{file_path}:{func.name}"] = func
        self.call_relationships.extend(relationships)

    def _resolve_call_relationships(self) -> None:
        func_lookup: Dict[str, str] = {}
        for fid, finfo in self.functions.items():
            func_lookup[fid] = fid
            func_lookup[finfo.name] = fid
            if finfo.component_id:
                func_lookup[finfo.component_id] = fid
                method_name = finfo.component_id.split(".")[-1]
                if method_name not in func_lookup:
                    func_lookup[method_name] = fid
        for rel in self.call_relationships:
            if rel.callee in func_lookup:
                rel.callee = func_lookup[rel.callee]
                rel.is_resolved = True
            elif "." in rel.callee:
                method_name = rel.callee.split(".")[-1]
                if method_name in func_lookup:
                    rel.callee = func_lookup[method_name]
                    rel.is_resolved = True

    def _deduplicate_relationships(self) -> None:
        seen: set = set()
        unique = []
        for rel in self.call_relationships:
            key = (rel.caller, rel.callee)
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        self.call_relationships = unique

    def _generate_visualization_data(self) -> Dict:
        cytoscape_elements = []
        for fid, finfo in self.functions.items():
            file_ext = Path(finfo.file_path).suffix.lower()
            cytoscape_elements.append(
                {
                    "data": {
                        "id": fid,
                        "label": finfo.name,
                        "file": finfo.file_path,
                        "type": finfo.node_type or "function",
                        "language": CODE_EXTENSIONS.get(file_ext, "unknown"),
                    },
                    "classes": (
                        "node-method"
                        if finfo.node_type == "method"
                        else "node-function"
                    ),
                }
            )
        for rel in self.call_relationships:
            if rel.is_resolved:
                cytoscape_elements.append(
                    {
                        "data": {
                            "id": f"{rel.caller}->{rel.callee}",
                            "source": rel.caller,
                            "target": rel.callee,
                            "line": rel.call_line,
                        },
                        "classes": "edge-call",
                    }
                )
        return {
            "cytoscape": {"elements": cytoscape_elements},
            "summary": {
                "total_nodes": len(self.functions),
                "total_edges": sum(1 for r in self.call_relationships if r.is_resolved),
            },
        }
