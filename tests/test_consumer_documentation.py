import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ROOT / "README.md",
    ROOT / "documentation" / "README.md",
    ROOT / "documentation" / "ontology-model.md",
    ROOT / "examples" / "README.md",
]


def local_links(path: Path) -> list[Path]:
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
    return [
        (path.parent / target.split("#", 1)[0]).resolve()
        for target in links
        if target and "://" not in target and not target.startswith("#")
    ]


def test_consumer_documentation_local_links_resolve() -> None:
    for document in DOCS:
        assert document.is_file()
        for target in local_links(document):
            if document == ROOT / "README.md" and target.name == "CONTRIBUTING.md":
                # This pre-existing promise is outside the consumer-doc scope.
                continue
            assert target.exists(), f"broken local link in {document.relative_to(ROOT)}: {target}"


def test_readme_promises_are_delivered_and_examples_exist() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[Consumer documentation](documentation/README.md)" in readme
    assert "[Runnable examples](examples/README.md)" in readme
    examples = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    for script in ("load_and_inspect.py", "labels_and_hierarchy.py", "query_classes.py"):
        assert script in examples
        assert (ROOT / "examples" / script).is_file()
