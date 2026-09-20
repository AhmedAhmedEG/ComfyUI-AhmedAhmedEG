"""AST-based code auditor to detect any stubs, empty functions, NotImplementedError, or placeholder markers."""

import ast
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_DIRS = ["core", "nodes"]
SUSPICIOUS_PATTERNS = [
    re.compile(r"#\s*(TODO|FIXME|STUB|PLACEHOLDER|XXX|\.\.\.)", re.IGNORECASE),
    re.compile(r"^\s*\.\.\.\s*$"),
]


class StubAuditor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.issues = []

    def visit_FunctionDef(self, node):
        self._check_body(node, f"Function '{node.name}'")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_body(node, f"AsyncFunction '{node.name}'")
        self.generic_visit(node)

    def _check_body(self, node, func_desc):
        body = node.body
        # Filter out docstrings
        effective_stmts = []
        for stmt in body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue
            effective_stmts.append(stmt)

        if not effective_stmts:
            self.issues.append((node.lineno, f"{func_desc} is completely empty (only docstring or nothing)"))
            return

        if len(effective_stmts) == 1:
            stmt = effective_stmts[0]
            if isinstance(stmt, ast.Pass):
                self.issues.append((node.lineno, f"{func_desc} contains only 'pass'"))
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is ...:
                self.issues.append((node.lineno, f"{func_desc} contains only '...'"))
            elif isinstance(stmt, ast.Raise):
                if isinstance(stmt.exc, ast.Call) and getattr(stmt.exc.func, "id", None) == "NotImplementedError":
                    self.issues.append((node.lineno, f"{func_desc} raises NotImplementedError"))
                elif isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                    self.issues.append((node.lineno, f"{func_desc} raises NotImplementedError"))


def audit_file(filepath):
    rel_path = os.path.relpath(filepath, REPO_ROOT)
    issues = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 1. AST Check
    try:
        tree = ast.parse(content, filename=filepath)
        auditor = StubAuditor(rel_path)
        auditor.visit(tree)
        issues.extend(auditor.issues)
    except SyntaxError as e:
        issues.append((e.lineno or 0, f"SyntaxError: {e}"))

    # 2. Line-by-line regex check
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(line):
                issues.append((i, f"Suspicious marker: {line.strip()}"))

    return rel_path, issues


def main():
    total_issues = 0
    checked_files = 0

    print("=== Scanning Codebase for Stubs, Empty Functions, and Placeholders ===")
    for d in TARGET_DIRS:
        full_d = os.path.join(REPO_ROOT, d)
        for root, _, files in os.walk(full_d):
            for f in files:
                if f.endswith(".py"):
                    checked_files += 1
                    fp = os.path.join(root, f)
                    rel, issues = audit_file(fp)
                    if issues:
                        print(f"\n[!] {rel}:")
                        for lno, msg in issues:
                            print(f"    L{lno}: {msg}")
                        total_issues += len(issues)

    print(f"\nAudit complete: Checked {checked_files} files.")
    if total_issues == 0:
        print("[SUCCESS] Zero stubs, empty functions, or placeholder markers found!")
    else:
        print(f"[FAILURE] Found {total_issues} issues that need resolution.")
    return total_issues


if __name__ == "__main__":
    exit(main())
