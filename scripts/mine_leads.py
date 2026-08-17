#!/usr/bin/env python3
"""
mine_leads.py — mine candidate reference leads and idea leads out of one
extracted source text, writing per-source CSVs that a downstream dedup
pass (consolidate_leads.py) can merge across many sources.

Two independent extraction modes, both optional and both writable in one
run:

  citations   Regex-mines a reference list and in-text citations out of a
              plain-text file. Fully mechanical -- no judgement calls.

  ideas       Normalizes a small JSON file of idea/claim leads (which YOU,
              the reading agent, must have already identified by actually
              reading the source) into the standard ideas CSV schema.
              This mode does not "extract" ideas on its own -- see
              --ideas-input below and the SKILL.md for why.

Everything a source needs is passed by flag; nothing is hard-coded to a
particular project layout.

Examples:

    # Mine reference leads only, from an extracted-text file:
    python mine_leads.py --mode citations \\
        --source-slug smith-2001-example \\
        --input ./extracted_text/smith-2001-example.txt \\
        --out-dir ./leads

    # Normalize an already-drafted ideas file into the ideas CSV:
    python mine_leads.py --mode ideas \\
        --source-slug smith-2001-example \\
        --ideas-input ./ideas_drafts/smith-2001-example.json \\
        --out-dir ./leads

    # Do both in one call:
    python mine_leads.py --mode both \\
        --source-slug smith-2001-example \\
        --input ./extracted_text/smith-2001-example.txt \\
        --ideas-input ./ideas_drafts/smith-2001-example.json \\
        --out-dir ./leads
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

REF_FIELDNAMES = [
    "source_slug",
    "cited_title",
    "cited_authors",
    "cited_year",
    "cited_venue",
    "identifier_as_printed",
    "lead_type",
    "theme",
    "where_in_source",
    "completeness",
]

IDEA_FIELDNAMES = [
    "source_slug",
    "idea",
    "where_stated",
    "theme",
    "priority",
    "suggested_search_targets",
]

# Anchored pattern: a reference line that starts with an author string and
# is immediately followed by "(YEAR)." -- e.g. "Smith, J. (2001)." This is
# the high-precision path; try it first.
ANCHORED_REF_PATTERN = re.compile(r"^([A-Za-z][a-zA-Z\s&.,]*?)\s*\((\d{4}[a-z]?)\)\.")

# In-text narrative citation, e.g. "Smith (2001)" or "Smith & Jones (2001, 2004)".
BODY_CITATION_PATTERN = re.compile(
    r"([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+)?)\s*\((\d{4}(?:,\s*\d{4})*[a-z]?)\)"
)

# Year at the head of an accumulated (blank-line-joined) reference paragraph.
PARAGRAPH_YEAR_PATTERN = re.compile(r"\((\d{4}[a-z]?)\)")


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def find_references_section(text: str, headings) -> str:
    """Return the text from the first matching heading to end-of-file, or
    the empty string if none of the headings appear."""
    for heading in headings:
        idx = text.find(heading)
        if idx != -1:
            return text[idx + len(heading):]
    return ""


def extract_references_anchored(refs_text: str, source_slug: str, theme: str,
                                 min_line_len: int, truncate_at: int):
    """High-precision pass: one reference per physical line, line starts
    with 'Author (Year).'. Works well when the extractor did not wrap
    reference paragraphs across lines."""
    refs = []
    seen = set()

    for line in refs_text.split("\n"):
        line = line.strip()
        if not line or len(line) < min_line_len:
            continue

        match = ANCHORED_REF_PATTERN.match(line)
        if not match:
            continue

        authors = re.sub(r",\s*$", "", match.group(1).strip())
        year = match.group(2)
        key = (authors, year)
        if key in seen:
            continue
        seen.add(key)

        refs.append({
            "source_slug": source_slug,
            "cited_title": "",
            "cited_authors": authors,
            "cited_year": year,
            "cited_venue": "",
            "identifier_as_printed": line[:truncate_at],
            "lead_type": "peer_reviewed_candidate",
            "theme": theme,
            "where_in_source": "references_list",
            "completeness": "full_citation",
        })

    return refs


def extract_references_paragraph(refs_text: str, source_slug: str, theme: str,
                                  min_line_len: int):
    """Fallback pass: treats blank-line-separated blocks as one reference
    each (handles extractors that wrap a reference across lines). Use this
    when the anchored pass finds too few references."""
    refs = []
    seen = set()
    current = ""

    def flush(buf):
        buf = buf.strip()
        if not buf or len(buf) < min_line_len:
            return None
        if buf in seen:
            return None
        seen.add(buf)

        year_match = PARAGRAPH_YEAR_PATTERN.search(buf)
        year = year_match.group(1) if year_match else ""
        authors = ""
        if year_match:
            authors = re.sub(r"[.,]\s*$", "", buf[: year_match.start()].strip())

        return {
            "source_slug": source_slug,
            "cited_title": "",
            "cited_authors": authors,
            "cited_year": year,
            "cited_venue": "",
            "identifier_as_printed": buf,
            "lead_type": "peer_reviewed_candidate",
            "theme": theme,
            "where_in_source": "references_list",
            "completeness": "full_citation",
        }

    for line in refs_text.split("\n"):
        line = line.strip()
        if not line:
            row = flush(current)
            if row:
                refs.append(row)
            current = ""
            continue
        current = f"{current} {line}".strip() if current else line

    row = flush(current)
    if row:
        refs.append(row)

    return refs


def extract_body_citations(text: str, source_slug: str, theme: str,
                            context_before: int, context_after: int):
    """Scan the whole text for narrative citations like 'Smith (2001)' and
    capture surrounding context as the printed identifier. These are
    partial leads -- a year and a surname, not a full citation -- so they
    are marked completeness=partial_citation and left for the human/agent
    to complete during verification."""
    citations = []
    seen = set()

    for match in BODY_CITATION_PATTERN.finditer(text):
        authors = match.group(1).strip()
        years = match.group(2).strip()
        key = (authors, years)
        if key in seen:
            continue
        seen.add(key)

        start = max(0, match.start() - context_before)
        end = min(len(text), match.end() + context_after)
        context = text[start:end].strip()

        citations.append({
            "source_slug": source_slug,
            "cited_title": "",
            "cited_authors": authors,
            "cited_year": years,
            "cited_venue": "",
            "identifier_as_printed": context,
            "lead_type": "peer_reviewed_candidate",
            "theme": theme,
            "where_in_source": "body_text",
            "completeness": "partial_citation",
        })

    return citations


def mine_citations(args):
    text = read_text(Path(args.input))

    refs_text = find_references_section(text, args.references_heading)
    section_refs = []
    if refs_text:
        section_refs = extract_references_anchored(
            refs_text, args.source_slug, args.theme, args.min_ref_line_len, args.truncate_at
        )
        if len(section_refs) < args.min_anchored_hits:
            print(
                f"  Anchored pass found only {len(section_refs)} references "
                f"(< --min-anchored-hits={args.min_anchored_hits}); "
                f"falling back to paragraph-accumulation pass.",
                file=sys.stderr,
            )
            section_refs = extract_references_paragraph(
                refs_text, args.source_slug, args.theme, args.min_ref_line_len
            )
    else:
        print(
            f"  No heading from {args.references_heading} found in {args.input}; "
            f"skipping reference-list pass (body-citation pass still runs).",
            file=sys.stderr,
        )

    body_refs = []
    if not args.skip_body_citations:
        body_refs = extract_body_citations(
            text, args.source_slug, args.theme, args.context_before, args.context_after
        )

    all_refs = section_refs + body_refs
    print(
        f"  References: {len(section_refs)} from reference list, "
        f"{len(body_refs)} from body text ({len(all_refs)} total)",
        file=sys.stderr,
    )

    out_path = Path(args.out_dir) / f"refs_{args.source_slug}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REF_FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_refs)
    print(f"  Wrote {out_path}", file=sys.stderr)
    return out_path


def mine_ideas(args):
    """Normalize a hand/agent-drafted JSON list of idea leads into the
    standard ideas CSV. Input JSON is a list of objects with at least
    'idea' and 'where_stated'; 'theme', 'priority', and
    'suggested_search_targets' are optional and get defaults filled in."""
    ideas_path = Path(args.ideas_input)
    with open(ideas_path, "r", encoding="utf-8") as f:
        raw_ideas = json.load(f)

    if not isinstance(raw_ideas, list):
        raise ValueError(f"{ideas_path} must contain a JSON array of idea objects")

    rows = []
    for i, entry in enumerate(raw_ideas):
        if "idea" not in entry or not entry["idea"].strip():
            print(f"  Skipping entry {i}: missing required 'idea' text", file=sys.stderr)
            continue
        if "where_stated" not in entry or not entry["where_stated"].strip():
            print(
                f"  Skipping entry {i} ({entry['idea'][:50]!r}...): "
                f"missing required 'where_stated' locator",
                file=sys.stderr,
            )
            continue

        rows.append({
            "source_slug": args.source_slug,
            "idea": entry["idea"].strip(),
            "where_stated": entry["where_stated"].strip(),
            "theme": entry.get("theme", args.theme).strip() or args.theme,
            "priority": str(entry.get("priority", args.default_priority)),
            "suggested_search_targets": entry.get("suggested_search_targets", ""),
        })

    out_path = Path(args.out_dir) / f"ideas_{args.source_slug}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=IDEA_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {len(rows)} idea leads to {out_path}", file=sys.stderr)
    return out_path


def build_parser():
    p = argparse.ArgumentParser(
        description="Mine reference leads and/or idea leads from one extracted source text.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--mode", choices=["citations", "ideas", "both"], default="citations",
        help="Which lead type(s) to mine this run.",
    )
    p.add_argument(
        "--source-slug", required=True,
        help="Short stable identifier for the source, e.g. 'smith-2001-example'. "
             "Used in output filenames and as the source_slug column.",
    )
    p.add_argument(
        "--input",
        help="Path to the extracted plain-text file (required for --mode citations/both).",
    )
    p.add_argument(
        "--ideas-input",
        help="Path to a JSON array of {idea, where_stated, theme?, priority?, "
             "suggested_search_targets?} objects (required for --mode ideas/both). "
             "You must draft this file yourself by reading the source -- see SKILL.md.",
    )
    p.add_argument(
        "--out-dir", default="./leads",
        help="Directory to write refs_<slug>.csv / ideas_<slug>.csv into.",
    )
    p.add_argument(
        "--theme", default="general",
        help="Default theme tag applied to mined leads that don't specify their own.",
    )
    p.add_argument(
        "--references-heading", nargs="+", default=["References", "Works Cited", "Bibliography"],
        help="Heading string(s) that mark the start of the reference list. Tried in order; "
             "first match wins.",
    )
    p.add_argument(
        "--min-ref-line-len", type=int, default=15,
        help="Minimum character length for a line/paragraph to be considered a candidate reference.",
    )
    p.add_argument(
        "--min-anchored-hits", type=int, default=1,
        help="If the anchored (one-reference-per-line) pass finds fewer than this many "
             "references, fall back to the paragraph-accumulation pass instead.",
    )
    p.add_argument(
        "--truncate-at", type=int, default=200,
        help="Max characters kept in identifier_as_printed for anchored-pass reference lines.",
    )
    p.add_argument(
        "--skip-body-citations", action="store_true",
        help="Skip the in-text 'Author (Year)' narrative-citation pass.",
    )
    p.add_argument(
        "--context-before", type=int, default=50,
        help="Characters of context captured before an in-text citation match.",
    )
    p.add_argument(
        "--context-after", type=int, default=150,
        help="Characters of context captured after an in-text citation match.",
    )
    p.add_argument(
        "--default-priority", default="1",
        help="Priority value stamped on idea leads that don't specify their own.",
    )
    return p


def main():
    args = build_parser().parse_args()

    if args.mode in ("citations", "both") and not args.input:
        build_parser().error("--input is required for --mode citations/both")
    if args.mode in ("ideas", "both") and not args.ideas_input:
        build_parser().error("--ideas-input is required for --mode ideas/both")

    print(f"Mining leads for source_slug={args.source_slug!r} (mode={args.mode})", file=sys.stderr)

    if args.mode in ("citations", "both"):
        mine_citations(args)

    if args.mode in ("ideas", "both"):
        mine_ideas(args)


if __name__ == "__main__":
    main()
