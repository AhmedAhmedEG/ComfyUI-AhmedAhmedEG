"""Build the offline HTML user guide and check public-node coverage."""
import ast
import base64
import json
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent


def build():
    data = json.loads((ROOT / "docs/guide_content.json").read_text(encoding="utf-8"))
    tree = ast.parse((ROOT / "nodes/__init__.py").read_text(encoding="utf-8"))
    names = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "NODE_DISPLAY_NAME_MAPPINGS" for t in n.targets))
    features = data["features"]
    assert len({s["id"] for s in features}) == len(features), "Duplicate feature IDs"
    covered = {node for s in features for node in s["nodes"]}
    assert covered == set(names), f"Node coverage mismatch: {covered ^ set(names)}"
    catalog = [{"id": key, "name": value, "feature": next(s["id"] for s in features if key in s["nodes"])}
               for key, value in names.items()]
    workflow = json.loads((ROOT / "workflows/MiniMax H3 Start Here.json").read_text(encoding="utf-8"))
    html = (ROOT / "docs/walkthrough_template.html").read_text(encoding="utf-8")
    for marker, value in [("__GUIDE_DATA__", data), ("__WORKFLOW_DATA__", workflow), ("__NODE_CATALOG__", catalog)]:
        assert html.count(marker) == 1
        html = html.replace(marker, json.dumps(value, ensure_ascii=False).replace("</", "<\\/"))
    assert html.count("__EDITOR_SCREENSHOT__") == 1
    screenshot = base64.b64encode((ROOT / "docs/master-editor.png").read_bytes()).decode("ascii")
    html = html.replace("__EDITOR_SCREENSHOT__", "data:image/png;base64," + screenshot)
    output = ROOT / "docs/MiniMax-H3-User-Guide.html"
    output.write_text(html, encoding="utf-8", newline="\n")
    print(f"Built practical guide with {len(features)} task topics covering {len(catalog)} public nodes: {output}")


if __name__ == "__main__":
    build()
