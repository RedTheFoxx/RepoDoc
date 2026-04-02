import ast
import logging
import warnings
from typing import List, Tuple, Optional
import os

from src.analysis.models.core import Node, CallRelationship

logger = logging.getLogger(__name__)


class PythonASTAnalyzer(ast.NodeVisitor):

    def __init__(self, file_path: str, content: str, repo_path: Optional[str] = None):
        self.file_path = file_path
        self.repo_path = repo_path
        self.content = content
        self.lines = content.splitlines()
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        self.current_class_name: str | None = None
        self.current_function_name: str | None = None
        self.top_level_nodes = {}

    def _get_relative_path(self) -> str:
        if self.repo_path:
            return os.path.relpath(self.file_path, self.repo_path)
        return str(self.file_path)

    def _get_module_path(self) -> str:
        try:
            relative_path = self._get_relative_path()
            path = relative_path
            for ext in [".py", ".pyx"]:
                if path.endswith(ext):
                    path = path[: -len(ext)]
                    break
            return path.replace("/", ".").replace("\\", ".")
        except Exception:
            return str(self.file_path).replace("/", ".").replace("\\", ".")

    def _get_component_id(self, name: str) -> str:
        module_path = self._get_module_path()
        if self.current_class_name:
            return f"{module_path}.{self.current_class_name}.{name}"
        return f"{module_path}.{name}"

    def visit_ClassDef(self, node: ast.ClassDef):
        base_classes = [self._extract_base_class_name(base) for base in node.bases]
        base_classes = [name for name in base_classes if name is not None]
        component_id = f"{self._get_module_path()}.{node.name}"
        relative_path = self._get_relative_path()
        class_node = Node(
            id=component_id,
            name=node.name,
            component_type="class",
            file_path=str(self.file_path),
            relative_path=relative_path,
            source_code="\n".join(
                self.lines[node.lineno - 1 : node.end_lineno or node.lineno]
            ),
            start_line=node.lineno,
            end_line=node.end_lineno,
            has_docstring=bool(ast.get_docstring(node)),
            docstring=ast.get_docstring(node) or "",
            parameters=None,
            node_type="class",
            base_classes=base_classes if base_classes else None,
            class_name=None,
            display_name=f"class {node.name}",
            component_id=component_id,
        )
        self.nodes.append(class_node)
        self.top_level_nodes[node.name] = class_node
        for base_name in base_classes:
            if base_name in self.top_level_nodes:
                self.call_relationships.append(
                    CallRelationship(
                        caller=component_id,
                        callee=f"{self._get_module_path()}.{base_name}",
                        call_line=node.lineno,
                        is_resolved=True,
                    )
                )
        self.current_class_name = node.name
        self.generic_visit(node)
        self.current_class_name = None

    def _extract_base_class_name(self, base):
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            parts = []
            n = base
            while isinstance(n, ast.Attribute):
                parts.append(n.attr)
                n = n.value
            if isinstance(n, ast.Name):
                parts.append(n.id)
            return ".".join(reversed(parts))
        return None

    def _process_function_node(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        if not self.current_class_name:
            component_id = f"{self._get_module_path()}.{node.name}"
            relative_path = self._get_relative_path()
            func_node = Node(
                id=component_id,
                name=node.name,
                component_type="function",
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code="\n".join(
                    self.lines[node.lineno - 1 : node.end_lineno or node.lineno]
                ),
                start_line=node.lineno,
                end_line=node.end_lineno,
                has_docstring=bool(ast.get_docstring(node)),
                docstring=ast.get_docstring(node) or "",
                parameters=[arg.arg for arg in node.args.args],
                node_type="function",
                base_classes=None,
                class_name=None,
                display_name=f"function {node.name}",
                component_id=component_id,
            )
            if self._should_include_function(func_node):
                self.nodes.append(func_node)
                self.top_level_nodes[node.name] = func_node
        self.current_function_name = node.name
        self.generic_visit(node)
        self.current_function_name = None

    def _should_include_function(self, func: Node) -> bool:
        if func.name.startswith("_test_"):
            return False
        return True

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function_node(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function_node(node)

    def visit_Call(self, node: ast.Call):
        if self.current_class_name or (
            self.current_function_name and not self.current_class_name
        ):
            call_name = self._get_call_name(node.func)
            if call_name:
                if self.current_class_name:
                    caller_id = f"{self._get_module_path()}.{self.current_class_name}"
                else:
                    caller_id = (
                        f"{self._get_module_path()}.{self.current_function_name}"
                    )
                callee_id = (
                    f"{self._get_module_path()}.{call_name}"
                    if call_name in self.top_level_nodes
                    else call_name
                )
                self.call_relationships.append(
                    CallRelationship(
                        caller=caller_id,
                        callee=callee_id,
                        call_line=node.lineno,
                        is_resolved=call_name in self.top_level_nodes,
                    )
                )
        self.generic_visit(node)

    def _get_call_name(self, node) -> str | None:
        PYTHON_BUILTINS = {
            "print",
            "len",
            "str",
            "int",
            "float",
            "bool",
            "list",
            "dict",
            "tuple",
            "set",
            "range",
            "enumerate",
            "zip",
            "isinstance",
            "hasattr",
            "getattr",
            "setattr",
            "open",
            "super",
            "__import__",
            "type",
            "object",
            "Exception",
            "ValueError",
            "TypeError",
            "KeyError",
            "IndexError",
            "AttributeError",
            "ImportError",
            "max",
            "min",
            "sum",
            "abs",
            "round",
            "sorted",
            "reversed",
            "filter",
            "map",
            "any",
            "all",
            "next",
            "iter",
            "callable",
            "repr",
            "format",
            "exec",
            "eval",
        }
        if isinstance(node, ast.Name):
            return None if node.id in PYTHON_BUILTINS else node.id
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                return (
                    None
                    if node.value.id in PYTHON_BUILTINS
                    else f"{node.value.id}.{node.attr}"
                )
            if isinstance(node.value, ast.Attribute):
                base_name = self._get_call_name(node.value)
                return f"{base_name}.{node.attr}" if base_name else node.attr
            return node.attr
        return None

    def analyze(self) -> None:
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=SyntaxWarning)
                tree = ast.parse(self.content)
            self.visit(tree)
        except SyntaxError as e:
            logger.warning("Could not parse %s: %s", self.file_path, e)
        except Exception as e:
            logger.error("Error analyzing %s: %s", self.file_path, e, exc_info=True)


def analyze_python_file(
    file_path: str, content: str, repo_path: Optional[str] = None
) -> Tuple[List[Node], List[CallRelationship]]:
    analyzer = PythonASTAnalyzer(file_path, content, repo_path)
    analyzer.analyze()
    return analyzer.nodes, analyzer.call_relationships
