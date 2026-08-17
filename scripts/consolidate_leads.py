#!/usr/bin/env python3
"""
consolidate_leads.py — merge many per-source refs_*.csv / ideas_*.csv files
(as produced by mine_leads.py) into deduplicated, cross-source-ranked
tables, plus a prioritized follow-up shortlist.

Outputs (written under --output-dir):

  reference_leads.csv   One row per unique reference, with cited_by_count
                         and cited_by_slugs showing how many/which sources
                         independently pointed at it. Sorted by
                         cited_by_count descending.

  hypothesis_leads.csv  One row per unique idea/claim lead, with
                         raised_by_slugs showing which sources raised it.
                         Sorted by priority ascending.

  shortlist.md          Top-N reference leads that cleared the
                         cited-by-count bar, grouped by theme, formatted as
                         a markdown checklist for a human/agent to verify
                         and acquire -- plus a "Gaps" section naming themes
                         that are thin on leads and may need a fresh
                         search rather than more mining.

Every reference lead in the output is stamped UNVERIFIED by construction:
this script never confirms a work exists, matches its printed metadata, or
is actually relevant. That confirmation is a separate, later step -- see
SKILL.md.

Example:

    python consolidate_leads.py --leads-dir ./leads --output-dir ./consolidated
"""

import argparse
import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


def normalize_key_text(text: str) -> str:
    """Lowercase, strip punctuation/diacritics, collapse whitespace -- so
    minor formatting differences between two mentions of the same work
    don't produce two dedup keys."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def source_slug_from_filename(path: Path, prefix: str) -> str:
    name = path.name
    if name.startswith(prefix) and name.endswith(".csv"):
        return name[len(prefix):-4]
    return name


def dedup_key_for_ref(row: dict) -> tuple:
    """Preferred key: (normalized title, year) -- the most specific
    signal available. Falls back to (normalized authors, year) when no
    title was captured (common for in-text citation leads), and finally
    to a normalized-identifier key so that no lead is silently dropped
    just because it lacks a title. This fallback chain is a deliberate
    improvement over dropping untitled leads outright: partial leads are
    still worth surfacing and counting cross-source corroboration for."""
    title = normalize_key_text(row.get("cited_title", ""))
    year = (row.get("cited_year") or "").strip()
    if title:
        return ("title", title, year)

    authors = normalize_key_text(row.get("cited_authors", ""))
    if authors:
        return ("authors", authors, year)

    identifier = normalize_key_text(row.get("identifier_as_printed", ""))
    return ("identifier", identifier[:120], year)


def read_refs_files(leads_dir: Path, prefix: str):
    refs_by_key = {}
    citing_slugs = defaultdict(list)

    files = sorted(leads_dir.glob(f"{prefix}*.csv"))
    print(f"Found {len(files)} reference-lead files", file=sys.stderr)

    for path in files:
        slug = source_slug_from_filename(path, prefix)
        try:
            with open(path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    key = dedup_key_for_ref(row)
                    if not any(key[1:]):
                        continue  # nothing usable to key on at all
                    if key not in refs_by_key:
                        refs_by_key[key] = row
                    if slug not in citing_slugs[key]:
                        citing_slugs[key].append(slug)
        except Exception as e:
            print(f"  Error reading {path}: {e}", file=sys.stderr)

    return refs_by_key, citing_slugs


def read_ideas_files(leads_dir: Path, prefix: str):
    ideas_by_text = {}
    raised_by = defaultdict(list)

    files = sorted(leads_dir.glob(f"{prefix}*.csv"))
    print(f"Found {len(files)} idea-lead files", file=sys.stderr)

    for path in files:
        slug = source_slug_from_filename(path, prefix)
        try:
            with open(path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    idea_text = (row.get("idea") or "").strip()
                    if not idea_text:
                        continue
                    key = normalize_key_text(idea_text)
                    if key not in ideas_by_text:
                        ideas_by_text[key] = row
                    if slug not in raised_by[key]:
                        raised_by[key].append(slug)
        except Exception as e:
            print(f"  Error reading {path}: {e}", file=sys.stderr)

    return ideas_by_text, raised_by


def get_priority(row: dict) -> int:
    try:
        return int(row.get("priority", 999))
    except (ValueError, TypeError):
        return 999


def write_reference_leads(refs_by_key, citing_slugs, output_path: Path):
    rows = []
    for key, row in refs_by_key.items():
        row = dict(row)
        slugs = citing_slugs.get(key, [])
        row["cited_by_count"] = len(slugs)
        row["cited_by_slugs"] = ";".join(slugs)
        rows.append(row)

    rows.sort(key=lambda r: (-int(r.get("cited_by_count", 0)), r.get("theme", "")))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fieldnames = [k for k in rows[0].keys() if k is not None]
        for extra in ("cited_by_count", "cited_by_slugs"):
            if extra not in fieldnames:
                fieldnames.append(extra)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    print(f"Wrote {len(rows)} reference leads to {output_path}", file=sys.stderr)
    return rows


def write_hypothesis_leads(ideas_by_text, raised_by, output_path: Path):
    rows = []
    for key, row in ideas_by_text.items():
        row = dict(row)
        slugs = raised_by.get(key, [])
        row["raised_by_slugs"] = ";".join(slugs)
        rows.append(row)

    rows.sort(key=get_priority)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        fieldnames = [k for k in rows[0].keys() if k is not None]
        if "raised_by_slugs" not in fieldnames:
            fieldnames.append("raised_by_slugs")
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    print(f"Wrote {len(rows)} hypothesis leads to {output_path}", file=sys.stderr)
    return rows


def format_citation(entry: dict) -> str:
    parts = []
    if entry.get("cited_authors"):
        parts.append(entry["cited_authors"])
    if entry.get("cited_year"):
        parts.append(f"({entry['cited_year']})")
    if entry.get("cited_title"):
        parts.append(f'"{entry["cited_title"]}"')
    if entry.get("cited_venue"):
        parts.append(f"in {entry['cited_venue']}")
    if parts:
        return " ".join(parts)
    return entry.get("identifier_as_printed", "")[:200] or "(no printed identifier captured)"


def write_shortlist(ref_rows, output_path: Path, min_citations: int, shortlist_size: int,
                     sparse_threshold: int):
    high_value = [r for r in ref_rows if int(r.get("cited_by_count", 0)) >= min_citations]
    top_entries = high_value[:shortlist_size]

    by_theme = defaultdict(list)
    for entry in top_entries:
        by_theme[entry.get("theme", "other")].append(entry)

    theme_totals = defaultdict(int)
    for r in ref_rows:
        theme_totals[r.get("theme", "other")] += 1
    sparse_themes = {t: c for t, c in theme_totals.items() if c <= sparse_threshold}

    lines = []
    lines.append("# Follow-Up Shortlist\n")
    lines.append(
        f"Reference leads cited by {min_citations}+ independent sources, ranked by "
        f"cross-source corroboration and grouped by theme. Every entry is a "
        f"**candidate** to verify -- not a confirmed, checked citation.\n"
    )

    for theme in sorted(by_theme.keys()):
        lines.append(f"\n## {theme.replace('-', ' ').title()}\n")
        for idx, entry in enumerate(by_theme[theme], 1):
            citation = format_citation(entry)
            count = entry.get("cited_by_count", 0)
            slugs = entry.get("cited_by_slugs", "")
            citing = ", ".join(slugs.split(";")) if slugs else "unknown"
            lines.append(f"### {idx}. {entry.get('cited_title') or citation}\n")
            lines.append(f"**Citation as printed:** {citation}\n")
            lines.append(f"**Cited by:** {citing} ({count} independent source(s))\n")
            lines.append("**Why it matters:** [fill in during verification]\n")
            lines.append(
                "**Status:** UNVERIFIED -- confirm the work exists, confirm the "
                "printed metadata, and read enough of it to confirm relevance "
                "before citing it anywhere.\n\n"
            )

    if sparse_themes:
        lines.append("\n## Gaps -- Themes Thin On Leads\n")
        lines.append(
            "These themes have few mined leads and may need a fresh, "
            "targeted literature search rather than more mining:\n\n"
        )
        for theme, count in sorted(sparse_themes.items(), key=lambda x: x[1]):
            lines.append(f"- **{theme.replace('-', ' ').title()}** ({count} lead(s))\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))

    print(f"Wrote shortlist ({len(top_entries)} entries) to {output_path}", file=sys.stderr)
    return len(top_entries)


def build_parser():
    p = argparse.ArgumentParser(
        description="Consolidate per-source reference/idea lead CSVs into deduplicated, "
                     "cross-source-ranked tables plus a follow-up shortlist.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--leads-dir", required=True,
        help="Directory containing refs_<slug>.csv and ideas_<slug>.csv files "
             "(as produced by mine_leads.py).",
    )
    p.add_argument(
        "--output-dir", required=True,
        help="Directory to write reference_leads.csv, hypothesis_leads.csv, and shortlist.md into.",
    )
    p.add_argument(
        "--refs-prefix", default="refs_",
        help="Filename prefix identifying reference-lead files in --leads-dir.",
    )
    p.add_argument(
        "--ideas-prefix", default="ideas_",
        help="Filename prefix identifying idea-lead files in --leads-dir.",
    )
    p.add_argument(
        "--min-citations-for-shortlist", type=int, default=2,
        help="A reference lead needs this many independent citing sources to make the shortlist.",
    )
    p.add_argument(
        "--shortlist-size", type=int, default=25,
        help="Maximum number of entries to include in shortlist.md.",
    )
    p.add_argument(
        "--sparse-theme-threshold", type=int, default=3,
        help="A theme with this many total leads or fewer is flagged as a gap in shortlist.md.",
    )
    return p


def main():
    args = build_parser().parse_args()
    leads_dir = Path(args.leads_dir)
    output_dir = Path(args.output_dir)

    print(f"Consolidating leads from {leads_dir}", file=sys.stderr)

    refs_by_key, citing_slugs = read_refs_files(leads_dir, args.refs_prefix)
    ideas_by_text, raised_by = read_ideas_files(leads_dir, args.ideas_prefix)
    print(
        f"Read {len(refs_by_key)} unique reference leads and "
        f"{len(ideas_by_text)} unique idea leads",
        file=sys.stderr,
    )

    ref_rows = write_reference_leads(refs_by_key, citing_slugs, output_dir / "reference_leads.csv")
    idea_rows = write_hypothesis_leads(ideas_by_text, raised_by, output_dir / "hypothesis_leads.csv")
    shortlist_count = write_shortlist(
        ref_rows, output_dir / "shortlist.md",
        args.min_citations_for_shortlist, args.shortlist_size, args.sparse_theme_threshold,
    )

    print("\n=== CONSOLIDATION SUMMARY ===", file=sys.stderr)
    print(f"Unique reference leads: {len(ref_rows)}", file=sys.stderr)
    print(f"Unique idea leads: {len(idea_rows)}", file=sys.stderr)
    print(f"Shortlist entries: {shortlist_count}", file=sys.stderr)
    for idx, row in enumerate(ref_rows[:5], 1):
        print(
            f"  {idx}. {row.get('cited_authors', '')} ({row.get('cited_year', '')}) "
            f"{row.get('cited_title', '')} -- cited by {row.get('cited_by_count', 0)} source(s)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
