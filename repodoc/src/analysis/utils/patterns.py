"""
Code analysis patterns for different programming languages.
"""

from typing import Dict, List

DEFAULT_IGNORE_PATTERNS = {
    ".github",
    ".vscode",
    ".git",
    ".gitignore",
    ".gitmodules",
    "examples",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "__pycache__",
    ".pytest_cache",
    ".coverage",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "yarn.lock",
    ".npm",
    ".yarn",
    ".pnpm-store",
    "bun.lock",
    "bun.lockb",
    "*.class",
    "*.jar",
    "*.war",
    "*.ear",
    "*.nar",
    ".gradle/",
    ".settings/",
    ".classpath",
    "gradle-app.setting",
    "*.gradle",
    ".project",
    "*.o",
    "*.obj",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.lib",
    "*.out",
    "*.a",
    "*.pdb",
    "*.suo",
    "*.user",
    "*.userosscache",
    "*.sln.docstates",
    "*.nupkg",
    "bin/",
    ".svn",
    ".hg",
    ".gitattributes",
    "*.svg",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.pdf",
    "*.mov",
    "*.mp4",
    "*.mp3",
    "*.wav",
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenv",
    ".idea",
    ".vscode",
    ".vs",
    "*.swo",
    "*.swn",
    "*.sublime-*",
    "*.log",
    "*.bak",
    "*.swp",
    "*.tmp",
    "*.temp",
    ".cache",
    ".sass-cache",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.egg-info",
    "*.egg",
    "*.whl",
    "*.so",
    ".docusaurus",
    "*.min.js",
    "*.min.css",
    "*.map",
    ".terraform",
    "*.tfstate*",
    "digest.txt",
    "*.ini",
    "tests",
    "test",
    "Tests",
    "Test",
    "examples",
    "Examples",
}

DEFAULT_INCLUDE_PATTERNS = [
    "*.py",
    "*.js",
    "*.ts",
    "*.jsx",
    "*.tsx",
    "*.java",
    "*.cpp",
    "*.c",
    "*.h",
    "*.cs",
    "*.go",
    "*.rs",
    "*.php",
    "*.rb",
    "*.swift",
    "*.kt",
    "*.scala",
    "*.clj",
    "*.hs",
    "*.ml",
    "*.html",
    "*.css",
    "*.scss",
    "*.sass",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.xml",
    "*.md",
    "*.txt",
    "*.toml",
    "*.cfg",
    "*.ini",
]

CODE_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".h++": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".cs": "csharp",
}

ENTRY_POINT_PATTERNS = {
    "main.py",
    "app.py",
    "server.py",
    "__main__.py",
    "run.py",
    "start.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "gunicorn.py",
    "index.js",
    "app.js",
    "server.js",
    "main.js",
    "index.ts",
    "app.ts",
    "server.ts",
    "main.ts",
    "start.js",
    "start.ts",
    "bootstrap.js",
    "bootstrap.ts",
    "entry.js",
    "entry.ts",
    "main.go",
    "cmd.go",
    "server.go",
    "app.go",
    "root.go",
    "start.go",
    "main.rs",
    "lib.rs",
    "server.rs",
    "app.rs",
    "start.rs",
    "bin.rs",
    "main.c",
    "main.cpp",
    "main.cc",
    "main.cxx",
    "app.c",
    "app.cpp",
    "start.c",
    "start.cpp",
    "entry.c",
    "entry.cpp",
    "index.php",
    "app.php",
    "bootstrap.php",
    "artisan",
    "console",
    "server.php",
    "start.php",
}

ENTRY_POINT_PATH_PATTERNS = [
    "cmd/main",
    "cmd/root",
    "cmd/server",
    "src/main",
    "src/app",
    "src/server",
    "bin/main",
    "bin/app",
    "bin/server",
    "app/main",
    "app/server",
    "app/start",
    "scripts/start",
    "scripts/run",
]

ENTRY_POINT_NAME_PATTERNS = [
    "main",
    "app",
    "server",
    "start",
    "run",
    "entry",
    "bootstrap",
    "init",
    "cmd",
    "cli",
    "daemon",
    "service",
    "worker",
    "launcher",
]

HIGH_CONNECTIVITY_PATTERNS = {
    "router",
    "controller",
    "service",
    "handler",
    "middleware",
    "api",
    "core",
    "engine",
    "manager",
    "processor",
    "client",
    "mod",
    "module",
    "pkg",
    "package",
    "lib",
    "util",
    "utils",
    "helper",
    "helpers",
    "express",
    "fastapi",
    "gin",
    "actix",
    "rocket",
    "db",
    "database",
    "model",
    "entity",
    "repo",
    "repository",
    "config",
    "settings",
    "constants",
    "types",
    "interfaces",
    "console",
    "text",
    "style",
    "render",
    "display",
    "format",
    "parse",
    "parser",
    "convert",
    "transform",
    "process",
    "table",
    "tree",
    "list",
    "grid",
    "layout",
    "widget",
    "color",
    "theme",
    "visual",
    "graphic",
    "draw",
    "paint",
    "file",
    "io",
    "stream",
    "buffer",
    "cache",
    "store",
    "base",
    "common",
    "shared",
    "global",
    "main",
    "index",
}

SOURCE_DIRECTORY_PATTERNS = [
    "src/",
    "lib/",
    "core/",
    "pkg/",
    "cmd/",
    "internal/",
    "crates/",
    "modules/",
    "include/",
    "source/",
    "components/",
    "services/",
    "utils/",
]

FUNCTION_DEFINITION_PATTERNS: Dict[str, List[str]] = {
    "python": ["def {name}"],
    "javascript": ["function {name}", "const {name}", "export {name}"],
    "typescript": ["function {name}", "const {name}", "export {name}"],
    "go": ["func {name}"],
    "rust": ["fn {name}", "pub fn {name}"],
    "c": ["void {name}", "int {name}", "{name}("],
    "cpp": ["void {name}", "int {name}", "{name}("],
    "php": [
        "function {name}",
        "public function {name}",
        "private function {name}",
        "protected function {name}",
    ],
    "general": ["{name}("],
}

CRITICAL_FUNCTION_NAMES = {
    "main",
    "index",
    "app",
    "server",
    "start",
    "init",
    "run",
    "new",
}

EXPORT_PATTERNS = [
    "export default",
    "module.exports =",
    "exports.",
    "pub fn main",
    "pub fn new",
    "pub fn",
    "func main",
    "func new",
    "int main",
    "void main",
    "public static void main",
    'if __name__ == "__main__"',
]


def get_function_patterns_for_language(language: str) -> List[str]:
    return FUNCTION_DEFINITION_PATTERNS.get(
        language.lower(), FUNCTION_DEFINITION_PATTERNS["general"]
    )


def is_entry_point_file(filename: str) -> bool:
    fn = filename.lower()
    if fn in ENTRY_POINT_PATTERNS:
        return True
    for p in ENTRY_POINT_NAME_PATTERNS:
        if p in fn and any(
            ext in fn for ext in [".py", ".js", ".ts", ".go", ".rs", ".c", ".cpp"]
        ):
            return True
    return False


def is_entry_point_path(filepath: str) -> bool:
    return any(p in filepath.lower() for p in ENTRY_POINT_PATH_PATTERNS)


def has_high_connectivity_potential(filename: str, filepath: str) -> bool:
    fn, fp = filename.lower(), filepath.lower()
    if any(p in fn for p in HIGH_CONNECTIVITY_PATTERNS):
        return True
    if any(p in fp for p in HIGH_CONNECTIVITY_PATTERNS):
        return True
    if any(p in fp for p in SOURCE_DIRECTORY_PATTERNS):
        return True
    return False


def is_critical_function(func_name: str, code_snippet: str | None = None) -> bool:
    if func_name.lower() in CRITICAL_FUNCTION_NAMES:
        return True
    if code_snippet and any(p in code_snippet.lower() for p in EXPORT_PATTERNS):
        return True
    return False


def find_fallback_entry_points(
    code_files: List[Dict], max_files: int = 5
) -> List[Dict]:
    out = []
    for fi in code_files:
        fn = fi["name"].lower()
        if any(p in fn for p in ["main", "app", "server", "start", "index"]):
            out.append(fi)
        elif is_entry_point_path(fi["path"]):
            out.append(fi)
    if not out:
        for fi in code_files:
            if fi["path"].count("/") <= 1:
                out.append(fi)

    def key(fi: Dict) -> int:
        s = 0
        s -= fi["path"].lower().count("/")
        if any(p in fi["name"].lower() for p in ["main", "app", "index"]):
            s -= 10
        if any(ext in fi["name"] for ext in [".py", ".js", ".go", ".rs"]):
            s -= 5
        return s

    out.sort(key=key)
    return out[:max_files]


def find_fallback_connectivity_files(
    code_files: List[Dict], max_files: int = 10
) -> List[Dict]:
    out = [
        fi
        for fi in code_files
        if any(
            p in fi["path"].lower() for p in ["src/", "lib/", "app/", "pkg/", "core/"]
        )
    ]
    if len(out) < max_files:
        for fi in code_files:
            if fi not in out:
                if any(
                    ext in fi["name"].lower()
                    for ext in [".py", ".js", ".ts", ".go", ".rs", ".c", ".cpp"]
                ):
                    if not any(
                        x in fi["name"].lower() for x in ["test", "spec", "_test"]
                    ):
                        out.append(fi)
    return out[:max_files]
