"""Validate sources and build a clean install ZIP from explicit project inputs."""
from pathlib import Path
import ast
import hashlib
import json
import re
import zipfile


def build(root=None):
    root = Path(root) if root else Path(__file__).absolute().parent.parent
    version = re.search(r'^version\s*=\s*"([^"]+)"',
        (root/"pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE).group(1)
    names = ["__init__.py", "LICENSE", "README.md", "REVIEW.md", "NODE_GUIDE.md",
        "FEATURE_PARITY.md", "THIRD_PARTY_NOTICE.md", "requirements.txt", "pyproject.toml", ".gitignore", ".gitattributes"]
    files = [root/name for name in names]
    for name in ("core", "nodes", "web", "workflows", "tests", "validation", "tools"):
        files += [p for p in (root/name).rglob("*") if p.is_file()
            and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo")]
    for path in files:
        if path.suffix == ".py": ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
        if path.suffix == ".json": json.loads(path.read_text(encoding="utf-8"))
        if path.suffix in (".py", ".js", ".md", ".json", ".toml", ".txt", ".cjs"):
            if re.search(r"CF-Access-Client-(Id|Secret)|cfast_[A-Za-z0-9]",path.read_text(encoding="utf-8")):
                raise ValueError(f"Credential marker in {path.relative_to(root)}")
    for path in (root/"workflows").glob("*.json"):
        data=json.loads(path.read_text(encoding="utf-8")); ids={n["id"]:n for n in data["nodes"]}
        for link_id,origin,slot,target,target_slot,kind in data["links"]:
            if link_id not in ids[origin]["outputs"][slot]["links"] or ids[target]["inputs"][target_slot]["link"] != link_id:
                raise ValueError(f"Invalid workflow link {link_id} in {path.name}")
    destination=root/"dist"/f"MiniMaxH3Director-{version}.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files): archive.write(path,"MiniMaxH3Director/"+path.relative_to(root).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None: raise RuntimeError("Corrupt release archive")
    print(f"{destination.name}: {len(files)} files, {destination.stat().st_size} bytes")
    print("SHA256:",hashlib.sha256(destination.read_bytes()).hexdigest())
    return destination


if __name__ == "__main__":
    build()
