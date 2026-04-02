"""Code change analysis using existing language analyzers.

This module provides diff analysis by leveraging the existing AST analyzers
in src/analysis/analyzers/ to detect API changes between file versions.
"""

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from src.analysis.analyzers.python import PythonASTAnalyzer

# Import JavaScript and TypeScript analyzers
try:
    from src.analysis.analyzers.javascript import TreeSitterJSAnalyzer
except ImportError:
    TreeSitterJSAnalyzer = None

try:
    from src.analysis.analyzers.typescript import TreeSitterTSAnalyzer
except ImportError:
    TreeSitterTSAnalyzer = None

try:
    from src.analysis.analyzers.java import TreeSitterJavaAnalyzer
except ImportError:
    TreeSitterJavaAnalyzer = None

try:
    from src.analysis.analyzers.csharp import TreeSitterCSharpAnalyzer
except ImportError:
    TreeSitterCSharpAnalyzer = None

try:
    from src.analysis.analyzers.c import TreeSitterCAnalyzer
except ImportError:
    TreeSitterCAnalyzer = None

try:
    from src.analysis.analyzers.cpp import TreeSitterCppAnalyzer
except ImportError:
    TreeSitterCppAnalyzer = None

try:
    from src.analysis.analyzers.php import TreeSitterPHPAnalyzer
except ImportError:
    TreeSitterPHPAnalyzer = None

try:
    from src.analysis.analyzers.go import GoASTAnalyzer
except ImportError:
    GoASTAnalyzer = None

try:
    from src.analysis.analyzers.rust import RustASTAnalyzer
except ImportError:
    RustASTAnalyzer = None

try:
    from src.analysis.analyzers.php import TreeSitterPHPAnalyzer
except ImportError:
    TreeSitterPHPAnalyzer = None


class ChangeType(Enum):
    API_SIGNATURE_CHANGED = "api_signature_changed"
    NEW_COMPONENT = "new_component"
    REMOVED_COMPONENT = "removed_component"
    DOCSTRING_CHANGED = "docstring_changed"
    CODE_BODY_CHANGED = "code_body_changed"
    COMMENT_ONLY = "comment_only"
    NO_CHANGE = "no_change"


@dataclass
class ComponentChange:
    name: str
    change_type: ChangeType
    file_path: str
    line_number: int = 0
    old_signature: Optional[str] = None
    new_signature: Optional[str] = None
    details: str = ""


@dataclass
class FileChangeAnalysis:
    file_path: str
    language: str
    changes: list[ComponentChange] = field(default_factory=list)
    has_important_changes: bool = False

    def get_affected_components(self) -> list[str]:
        return [
            c.name for c in self.changes if c.change_type != ChangeType.COMMENT_ONLY
        ]


def analyze_python_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze Python file changes using the existing PythonASTAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="python")

    if old_content == new_content:
        return analysis

    old_analyzer = PythonASTAnalyzer(file_path, old_content)
    new_analyzer = PythonASTAnalyzer(file_path, new_content)

    try:
        old_analyzer.analyze()
    except Exception:
        pass

    try:
        new_analyzer.analyze()
    except Exception:
        pass

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        elif old_node.docstring != new_node.docstring:
            if old_node.docstring and new_node.docstring:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.DOCSTRING_CHANGED,
                        file_path=file_path,
                        details="Only docstring changed",
                    )
                )
            else:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.CODE_BODY_CHANGED,
                        file_path=file_path,
                        details="Code body or docstring changed",
                    )
                )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_javascript_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze JavaScript file changes using the existing TreeSitterJSAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="javascript")

    if old_content == new_content:
        return analysis

    if TreeSitterJSAnalyzer is None:
        analysis.has_important_changes = old_content != new_content
        if old_content != new_content:
            analysis.changes.append(
                ComponentChange(
                    name="<file_changed>",
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    details="JavaScript analyzer not available",
                )
            )
        return analysis

    old_analyzer = TreeSitterJSAnalyzer(file_path, old_content)
    new_analyzer = TreeSitterJSAnalyzer(file_path, new_content)

    try:
        old_analyzer.analyze()
    except Exception:
        pass

    try:
        new_analyzer.analyze()
    except Exception:
        pass

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        elif old_node.docstring != new_node.docstring:
            if old_node.docstring and new_node.docstring:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.DOCSTRING_CHANGED,
                        file_path=file_path,
                        details="Only docstring changed",
                    )
                )
            else:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.CODE_BODY_CHANGED,
                        file_path=file_path,
                        details="Code body or docstring changed",
                    )
                )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_typescript_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze TypeScript file changes using the existing TreeSitterTSAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="typescript")

    if old_content == new_content:
        return analysis

    if TreeSitterTSAnalyzer is None:
        analysis.has_important_changes = old_content != new_content
        if old_content != new_content:
            analysis.changes.append(
                ComponentChange(
                    name="<file_changed>",
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    details="TypeScript analyzer not available",
                )
            )
        return analysis

    old_analyzer = TreeSitterTSAnalyzer(file_path, old_content)
    new_analyzer = TreeSitterTSAnalyzer(file_path, new_content)

    try:
        old_analyzer.analyze()
    except Exception:
        pass

    try:
        new_analyzer.analyze()
    except Exception:
        pass

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        elif old_node.docstring != new_node.docstring:
            if old_node.docstring and new_node.docstring:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.DOCSTRING_CHANGED,
                        file_path=file_path,
                        details="Only docstring changed",
                    )
                )
            else:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.CODE_BODY_CHANGED,
                        file_path=file_path,
                        details="Code body or docstring changed",
                    )
                )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_java_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze Java file changes using the existing TreeSitterJavaAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="java")

    if old_content == new_content:
        return analysis

    if TreeSitterJavaAnalyzer is None:
        analysis.has_important_changes = old_content != new_content
        if old_content != new_content:
            analysis.changes.append(
                ComponentChange(
                    name="<file_changed>",
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    details="Java analyzer not available",
                )
            )
        return analysis

    old_analyzer = TreeSitterJavaAnalyzer(file_path, old_content)
    new_analyzer = TreeSitterJavaAnalyzer(file_path, new_content)

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        elif old_node.docstring != new_node.docstring:
            if old_node.docstring and new_node.docstring:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.DOCSTRING_CHANGED,
                        file_path=file_path,
                        details="Only docstring changed",
                    )
                )
            else:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.CODE_BODY_CHANGED,
                        file_path=file_path,
                        details="Code body or docstring changed",
                    )
                )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_csharp_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze C# file changes using the existing TreeSitterCSharpAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="csharp")

    if old_content == new_content:
        return analysis

    if TreeSitterCSharpAnalyzer is None:
        analysis.has_important_changes = old_content != new_content
        if old_content != new_content:
            analysis.changes.append(
                ComponentChange(
                    name="<file_changed>",
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    details="C# analyzer not available",
                )
            )
        return analysis

    old_analyzer = TreeSitterCSharpAnalyzer(file_path, old_content)
    new_analyzer = TreeSitterCSharpAnalyzer(file_path, new_content)

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        elif old_node.docstring != new_node.docstring:
            if old_node.docstring and new_node.docstring:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.DOCSTRING_CHANGED,
                        file_path=file_path,
                        details="Only docstring changed",
                    )
                )
            else:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.CODE_BODY_CHANGED,
                        file_path=file_path,
                        details="Code body or docstring changed",
                    )
                )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_c_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze C file changes using the existing TreeSitterCAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="c")

    if old_content == new_content:
        return analysis

    if TreeSitterCAnalyzer is None:
        analysis.has_important_changes = old_content != new_content
        if old_content != new_content:
            analysis.changes.append(
                ComponentChange(
                    name="<file_changed>",
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    details="C analyzer not available",
                )
            )
        return analysis

    old_analyzer = TreeSitterCAnalyzer(file_path, old_content)
    new_analyzer = TreeSitterCAnalyzer(file_path, new_content)

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_cpp_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze C++ file changes using the existing TreeSitterCppAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="cpp")

    if old_content == new_content:
        return analysis

    if TreeSitterCppAnalyzer is None:
        analysis.has_important_changes = old_content != new_content
        if old_content != new_content:
            analysis.changes.append(
                ComponentChange(
                    name="<file_changed>",
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    details="C++ analyzer not available",
                )
            )
        return analysis

    old_analyzer = TreeSitterCppAnalyzer(file_path, old_content)
    new_analyzer = TreeSitterCppAnalyzer(file_path, new_content)

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_php_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze PHP file changes using the existing TreeSitterPHPAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="php")

    if old_content == new_content:
        return analysis

    if TreeSitterPHPAnalyzer is None:
        analysis.has_important_changes = old_content != new_content
        if old_content != new_content:
            analysis.changes.append(
                ComponentChange(
                    name="<file_changed>",
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    details="PHP analyzer not available",
                )
            )
        return analysis

    old_analyzer = TreeSitterPHPAnalyzer(file_path, old_content)
    new_analyzer = TreeSitterPHPAnalyzer(file_path, new_content)

    old_components = {n.name: n for n in old_analyzer.nodes if n.name}
    new_components = {n.name: n for n in new_analyzer.nodes if n.name}

    old_names = set(old_components.keys())
    new_names = set(new_components.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_components[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_components[name]
        new_node = new_components[name]

        old_params = old_node.parameters or []
        new_params = new_node.parameters or []

        if old_params != new_params:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.API_SIGNATURE_CHANGED,
                    file_path=file_path,
                    old_signature=str(old_params),
                    new_signature=str(new_params),
                    details="Parameters changed",
                )
            )
        elif old_node.docstring != new_node.docstring:
            if old_node.docstring and new_node.docstring:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.DOCSTRING_CHANGED,
                        file_path=file_path,
                        details="Only docstring changed",
                    )
                )
            else:
                analysis.changes.append(
                    ComponentChange(
                        name=name,
                        change_type=ChangeType.CODE_BODY_CHANGED,
                        file_path=file_path,
                        details="Code body or docstring changed",
                    )
                )
        else:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Only internal code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_go_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze Go file changes using the GoASTAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="go")

    if old_content == new_content:
        return analysis

    if GoASTAnalyzer is None:
        return analysis

    old_analyzer = GoASTAnalyzer(file_path, old_content)
    new_analyzer = GoASTAnalyzer(file_path, new_content)

    try:
        old_analyzer.analyze()
    except Exception:
        pass

    try:
        new_analyzer.analyze()
    except Exception:
        pass

    old_nodes = {n.name: n for n in old_analyzer.nodes}
    new_nodes = {n.name: n for n in new_analyzer.nodes}

    old_names = set(old_nodes.keys())
    new_names = set(new_nodes.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_nodes[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_nodes[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_nodes[name]
        new_node = new_nodes[name]

        if old_node.source_code != new_node.source_code:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Source code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
        ChangeType.CODE_BODY_CHANGED,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis


def analyze_rust_diff(
    file_path: str, old_content: str, new_content: str
) -> FileChangeAnalysis:
    """Analyze Rust file changes using the RustASTAnalyzer."""
    analysis = FileChangeAnalysis(file_path=file_path, language="rust")

    if old_content == new_content:
        return analysis

    if RustASTAnalyzer is None:
        return analysis

    old_analyzer = RustASTAnalyzer(file_path, old_content)
    new_analyzer = RustASTAnalyzer(file_path, new_content)

    try:
        old_analyzer.analyze()
    except Exception:
        pass

    try:
        new_analyzer.analyze()
    except Exception:
        pass

    old_nodes = {n.name: n for n in old_analyzer.nodes}
    new_nodes = {n.name: n for n in new_analyzer.nodes}

    old_names = set(old_nodes.keys())
    new_names = set(new_nodes.keys())

    added = new_names - old_names
    removed = old_names - new_names
    common = old_names & new_names

    for name in added:
        node = new_nodes[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.NEW_COMPONENT,
                file_path=file_path,
                details=f"New {node.component_type} added",
            )
        )

    for name in removed:
        node = old_nodes[name]
        analysis.changes.append(
            ComponentChange(
                name=name,
                change_type=ChangeType.REMOVED_COMPONENT,
                file_path=file_path,
                details=f"{node.component_type} removed",
            )
        )

    for name in common:
        old_node = old_nodes[name]
        new_node = new_nodes[name]

        if old_node.source_code != new_node.source_code:
            analysis.changes.append(
                ComponentChange(
                    name=name,
                    change_type=ChangeType.CODE_BODY_CHANGED,
                    file_path=file_path,
                    details="Source code changed",
                )
            )

    important_types = {
        ChangeType.API_SIGNATURE_CHANGED,
        ChangeType.NEW_COMPONENT,
        ChangeType.REMOVED_COMPONENT,
    }
    analysis.has_important_changes = any(
        c.change_type in important_types for c in analysis.changes
    )

    return analysis





LANGUAGE_ANALYZERS = {
    ".py": analyze_python_diff,
    ".js": analyze_javascript_diff,
    ".jsx": analyze_javascript_diff,
    ".ts": analyze_typescript_diff,
    ".tsx": analyze_typescript_diff,
    ".java": analyze_java_diff,
    ".cs": analyze_csharp_diff,
    ".c": analyze_c_diff,
    ".cpp": analyze_cpp_diff,
    ".cc": analyze_cpp_diff,
    ".cxx": analyze_cpp_diff,
    ".h": analyze_c_diff,
    ".hpp": analyze_cpp_diff,
    ".php": analyze_php_diff,
    ".go": analyze_go_diff,
    ".rs": analyze_rust_diff,
}


def get_diff_analyzer(file_path: str):
    """Get the appropriate diff analyzer for a file."""
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_ANALYZERS.get(ext, None)


def _is_test_file(file_path: str) -> bool:
    """Check if a file is a test file."""
    path = Path(file_path)
    name = path.name.lower()
    parent = path.parent.name.lower()

    # Common test file patterns
    test_patterns = [
        "test_",
        "_test.",
        "tests",
        "test",
    ]

    # Check filename patterns
    for pattern in test_patterns:
        if pattern in name:
            return True

    # Check if in tests directory
    if "tests" in path.parts or parent == "test":
        return True

    return False


def analyze_git_diff(
    repo_path: str,
    base_commit: Optional[str] = None,
    include_tests: bool = False,
) -> dict[str, FileChangeAnalysis]:
    """Analyze git diff to find important code changes.

    Args:
        repo_path: Path to the repository
        base_commit: Base commit to compare against
        include_tests: Whether to include test files in analysis (default: False)
    """

    if base_commit:
        cmd = ["git", "diff", "--name-only", base_commit]
    else:
        cmd = ["git", "diff", "--name-only", "HEAD"]

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    changed_files = result.stdout.strip().split("\n")
    changed_files = [f for f in changed_files if f]

    # Filter out test files by default
    if not include_tests:
        changed_files = [f for f in changed_files if not _is_test_file(f)]

    analyses = {}

    for file_path in changed_files:
        full_path = Path(repo_path) / file_path
        if not full_path.exists():
            continue

        try:
            new_content = full_path.read_text()
        except Exception:
            continue

        if base_commit:
            cmd = ["git", "show", f"{base_commit}:{file_path}"]
        else:
            cmd = ["git", "show", f"HEAD:{file_path}"]

        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)

        if result.returncode == 0:
            old_content = result.stdout
        else:
            old_content = ""

        analyzer = get_diff_analyzer(file_path)

        if analyzer:
            analysis = analyzer(file_path, old_content, new_content)
        else:
            # Skip files without AST analyzer - these are non-code files (RST, MD, etc.)
            # They don't affect API documentation
            continue

        analyses[file_path] = analysis

    return analyses


def filter_important_changes(
    analyses: dict[str, FileChangeAnalysis],
) -> dict[str, FileChangeAnalysis]:
    """Filter to only files with important API-affecting changes."""
    important = {}

    for file_path, analysis in analyses.items():
        if analysis.has_important_changes:
            important[file_path] = analysis

    return important
