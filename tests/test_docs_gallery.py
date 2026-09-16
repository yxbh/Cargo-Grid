"""Documentation coverage and assets without requiring a renderer or Pillow."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from cargo_grid.catalogue import accessory_variants

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gallery():
    spec = importlib.util.spec_from_file_location("docs_gallery", ROOT / "tools/render_docs.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_gallery_covers_every_bounded_catalogue_variant_once(gallery):
    items = gallery.inventory()
    assert [item.spec for item in items] == accessory_variants(gallery.BUILD)
    assert len(items) == len({item.key for item in items}) == 41
    rendered = [
        item.key for family in gallery.FAMILIES for item in items if item.spec.family == family
    ]
    assert sorted(rendered) == sorted(item.key for item in items)
    assert set(gallery.FAMILIES) == {item.spec.family for item in items}


def test_documented_assets_are_bounded_and_inventory_is_complete(gallery):
    assets = gallery.verify_assets()
    assert set(assets) == {
        *gallery.IMAGE_NAMES,
        *(f"attachments/{item.key}.png" for item in gallery.inventory()),
    }
    assert sum(asset["bytes"] for asset in assets.values()) <= 2_000_000


def test_thumbnail_manifest_has_unique_rows_and_family_scale(gallery):
    manifest = json.loads((ROOT / "docs/images/attachments/manifest.json").read_text())
    assert manifest["geometry_commit"] == gallery.GEOMETRY_REVISION
    assert manifest["workbench_commit"] == gallery.WORKBENCH_REVISION
    entries = manifest["items"]
    for field in ("file", "key", "public_name", "alt", "sha256"):
        assert len({entry[field] for entry in entries}) == 41
    for family in gallery.FAMILIES:
        rows = [entry for entry in entries if entry["family"] == family]
        assert len({entry["pixels_per_mm"] for entry in rows}) == 1
    assert all(entry["dimensions"] == [480, 300] for entry in entries)
    assert "docs/attachments.md" in (ROOT / "README.md").read_text()


def test_bracket_family_context_is_separate_from_the_part_inventory(gallery):
    assert [item.key for item in gallery.bracket_assembly_items()] == [
        "bracket-context-1x2",
        "bracket-context-2x1",
        "bracket-context-2x2",
    ]
    assert len(gallery.documentation_shape("bracket-context-1x2").solids()) == 2
    assert len(gallery.documentation_shape("vertical-tile-bracket-1x2").solids()) == 1


def test_provenance_hashes_can_wrap_without_changing_their_text(gallery):
    revision = gallery.GEOMETRY_REVISION
    tag = gallery.revision_tag(revision)
    assert tag.replace("<code>", "").replace("</code>", "").replace("<wbr>", "") == revision
    assert all(
        len(piece) <= 8
        for piece in tag.removeprefix("<code>").removesuffix("</code>").split("<wbr>")
    )


def test_thumbnail_checks_reject_a_wrong_hash(gallery, tmp_path, monkeypatch):
    import shutil

    docs = tmp_path / "docs"
    shutil.copytree(ROOT / "docs/images", docs / "images")
    shutil.copy2(ROOT / "docs/attachments.md", docs / "attachments.md")
    path = docs / "images/attachments/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["items"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(gallery, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="hash mismatch"):
        gallery.verify_assets()


@pytest.mark.parametrize("document", ["README.md", "AGENTS.md", "docs/attachments.md"])
def test_document_links_resolve_without_private_or_remote_paths(document):
    path = ROOT / document
    text = path.read_text()
    assert not re.search(r"/Users/|/Applications/|OneDrive|copilot-worktrees", text)
    targets = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r'(?:src|href)="([^"]+)"', text)
    for target in targets:
        target = target.split("#", 1)[0]
        if not target:
            continue
        assert "://" not in target, target
        assert not Path(target).is_absolute(), target
        assert (path.parent / target).exists(), target


def test_only_named_docs_images_are_distribution_exceptions(gallery):
    spec = importlib.util.spec_from_file_location(
        "distribution_gate", ROOT / "tools/check_distributions.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DOCUMENTATION_IMAGES == {
        *(f"docs/images/{name}" for name in gallery.IMAGE_NAMES),
        *(f"docs/images/attachments/{item.key}.png" for item in gallery.inventory()),
    }
    for name in ("docs/images/unapproved.png", "outputs/render.png", "docs/images/hero.step"):
        with pytest.raises(ValueError):
            module.check_path(name)
