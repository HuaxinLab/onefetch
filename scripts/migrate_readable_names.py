#!/usr/bin/env python3
"""One-time migration: rename data/ dirs to human-readable names.

Usage:
    python scripts/migrate_readable_names.py [--dry-run]

Renames:
- data/<timestamp-hash>/ -> data/<slugified_title>-<date>-<hash>/
- data/collections/seed-<hash>/ -> data/collections/<slugified_title>-<hash8>/
- items inside collections: 001-<timestamp-hash> -> 001-<slugified_title>-<date>-<hash>
- Updates manifest.json (collection_key, feed_path) and catalog.jsonl (article_dir)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Add project root to path so we can import slugify_title
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from onefetch.storage import slugify_title

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_ITEM_PREFIX_RE = re.compile(r"^(\d{3})-(.*)$")


def _new_article_dirname(old_name: str, title: str) -> str:
    """Generate new dirname for a single-page article dir."""
    slug = slugify_title(title)
    # Extract date (first 8 digits) and hash (last 8 chars) from old name
    # Old format: 20260320-091449-b5471b05 or slugified-20260320-b5471b05
    parts = old_name.rsplit("-", 1)
    short_hash = parts[-1] if len(parts) > 1 else old_name[-8:]
    # Find date: look for 8-digit sequence
    date_match = re.search(r"(\d{8})", old_name)
    date_str = date_match.group(1) if date_match else "00000000"
    if slug:
        return f"{slug}-{date_str}-{short_hash}"
    return old_name  # fallback: keep as-is


def _new_collection_dirname(old_name: str, title: str) -> str:
    """Generate new dirname for a collection dir."""
    slug = slugify_title(title)
    # old_name like "seed-02bd2a6fc9679f08"
    short_hash = old_name.split("-", 1)[-1][:8] if "-" in old_name else old_name[:8]
    if slug:
        return f"{slug}-{short_hash}"
    return old_name


def migrate_single_articles(dry_run: bool) -> dict[str, str]:
    """Rename data/<timestamp-hash>/ dirs. Returns {old_abs: new_abs}."""
    renames: dict[str, str] = {}
    for d in sorted(DATA_DIR.iterdir()):
        if not d.is_dir() or d.name in ("collections", ".DS_Store"):
            continue
        feed_path = d / "feed.json"
        if not feed_path.exists():
            continue
        try:
            feed = json.loads(feed_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        title = feed.get("title", "")
        new_name = _new_article_dirname(d.name, title)
        if new_name == d.name:
            continue
        new_path = DATA_DIR / new_name
        if new_path.exists():
            print(f"  SKIP (target exists): {d.name} -> {new_name}")
            continue
        print(f"  {d.name} -> {new_name}")
        if not dry_run:
            d.rename(new_path)
        renames[str(d)] = str(new_path)
    return renames


def migrate_collections(dry_run: bool) -> dict[str, str]:
    """Rename collection dirs and their items. Returns {old_abs: new_abs}."""
    collections_dir = DATA_DIR / "collections"
    if not collections_dir.exists():
        return {}

    renames: dict[str, str] = {}

    for coll_dir in sorted(collections_dir.iterdir()):
        if not coll_dir.is_dir() or coll_dir.name == ".DS_Store":
            continue
        manifest_path = coll_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        # Get collection title from first item
        items = manifest.get("items", [])
        coll_title = items[0].get("title", "") if items else ""

        # Rename items inside the collection
        items_dir = coll_dir / "items"
        item_renames: dict[str, str] = {}  # old_feed_path -> new_feed_path (relative)
        if items_dir.exists():
            for item_dir in sorted(items_dir.iterdir()):
                if not item_dir.is_dir():
                    continue
                feed_path = item_dir / "feed.json"
                if not feed_path.exists():
                    continue
                try:
                    feed = json.loads(feed_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                item_title = feed.get("title", "")
                # Parse existing name: 001-20260323-121914-d6ab8359
                m = _ITEM_PREFIX_RE.match(item_dir.name)
                if m:
                    seq = m.group(1)
                    old_suffix = m.group(2)
                    new_suffix = _new_article_dirname(old_suffix, item_title)
                    new_item_name = f"{seq}-{new_suffix}"
                else:
                    new_item_name = _new_article_dirname(item_dir.name, item_title)

                if new_item_name != item_dir.name:
                    new_item_path = items_dir / new_item_name
                    if new_item_path.exists():
                        print(f"    SKIP item (exists): {item_dir.name} -> {new_item_name}")
                        continue
                    print(f"    {item_dir.name} -> {new_item_name}")
                    old_rel = f"items/{item_dir.name}"
                    new_rel = f"items/{new_item_name}"
                    item_renames[old_rel] = new_rel
                    if not dry_run:
                        item_dir.rename(new_item_path)

        # Rename collection dir itself
        new_coll_name = _new_collection_dirname(coll_dir.name, coll_title)
        print(f"  {coll_dir.name} -> {new_coll_name}")

        # Update manifest.json (feed_path references + collection_key)
        if not dry_run:
            # Update feed_path in items
            for item in items:
                old_fp = item.get("feed_path", "")
                if old_fp in item_renames:
                    item["feed_path"] = item_renames[old_fp]
            manifest["collection_key"] = new_coll_name
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        if new_coll_name != coll_dir.name:
            new_coll_path = collections_dir / new_coll_name
            if new_coll_path.exists():
                print(f"  SKIP collection (exists): {coll_dir.name} -> {new_coll_name}")
                # Still track item renames for catalog update
                for old_rel, new_rel in item_renames.items():
                    old_abs = str(coll_dir / old_rel)
                    new_abs = str(coll_dir / new_rel)
                    renames[old_abs] = new_abs
                continue
            if not dry_run:
                coll_dir.rename(new_coll_path)
            # Track all paths under this collection for catalog rewrite
            for old_rel, new_rel in item_renames.items():
                old_abs = str(coll_dir / old_rel)
                new_abs = str(new_coll_path / new_rel)
                renames[old_abs] = new_abs
            # Items that weren't renamed still moved because parent dir renamed
            if items_dir.exists() or (not dry_run and (new_coll_path / "items").exists()):
                src_items = new_coll_path / "items" if not dry_run else items_dir
                for item_dir in sorted((src_items if src_items.exists() else items_dir).iterdir()):
                    if not item_dir.is_dir():
                        continue
                    old_abs = str(coll_dir / "items" / item_dir.name)
                    new_abs = str(new_coll_path / "items" / item_dir.name)
                    if old_abs not in renames:
                        renames[old_abs] = new_abs
        else:
            for old_rel, new_rel in item_renames.items():
                old_abs = str(coll_dir / old_rel)
                new_abs = str(coll_dir / new_rel)
                renames[old_abs] = new_abs

    return renames


def update_catalog(renames: dict[str, str], dry_run: bool) -> None:
    """Rewrite catalog.jsonl to reflect renamed paths."""
    catalog_path = DATA_DIR / "catalog.jsonl"
    if not catalog_path.exists():
        return

    records: list[dict] = []
    changed = False
    for line in catalog_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        old_dir = str(rec.get("article_dir", ""))
        if old_dir in renames:
            rec["article_dir"] = renames[old_dir]
            changed = True
        records.append(rec)

    if changed:
        print(f"\n  Updating catalog.jsonl ({sum(1 for o in renames if any(r.get('article_dir') == renames[o] for r in records))} paths)")
        if not dry_run:
            catalog_path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                encoding="utf-8",
            )


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN (no changes will be made) ===\n")

    print("Renaming single-page articles:")
    article_renames = migrate_single_articles(dry_run)
    print(f"  Total: {len(article_renames)}\n")

    print("Renaming collections:")
    collection_renames = migrate_collections(dry_run)
    print(f"  Total: {len(collection_renames)}\n")

    all_renames = {**article_renames, **collection_renames}
    if all_renames:
        print("Updating catalog.jsonl:")
        update_catalog(all_renames, dry_run)

    print(f"\nDone! {'(dry run)' if dry_run else ''}")


if __name__ == "__main__":
    main()
