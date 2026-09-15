"""Documentation coverage and assets without requiring a renderer or Pillow."""

import importlib.util
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
    assert len(items) == len({item.key for item in items}) == 44
    rendered = [
        item.key
        for _, _, families, _ in gallery.SHEETS
        for item in items
        if item.spec.family in families
    ]
    assert sorted(rendered) == sorted(item.key for item in items)
    assert [
        sum(item.spec.family in families for item in items) for _, _, families, _ in gallery.SHEETS
    ] == [15, 18, 11]


def test_documented_assets_are_bounded_and_inventory_is_complete(gallery):
    assets = gallery.verify_assets()
    assert set(assets) == set(gallery.IMAGE_NAMES)
    assert sum(asset["bytes"] for asset in assets.values()) <= 4_000_000


@pytest.mark.parametrize("document", ["README.md", "AGENTS.md", "docs/attachments.md"])
def test_document_links_resolve_without_private_or_remote_paths(document):
    path = ROOT / document
    text = path.read_text()
    assert not re.search(r"/Users/|/Applications/|OneDrive|copilot-worktrees", text)
    for target in re.findall(r"\]\(([^)]+)\)", text):
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
    assert module.DOCUMENTATION_IMAGES == {f"docs/images/{name}" for name in gallery.IMAGE_NAMES}
    for name in ("docs/images/unapproved.png", "outputs/render.png", "docs/images/hero.step"):
        with pytest.raises(ValueError):
            module.check_path(name)
