---
name: citation-lead-mining-and-dedup
description: Mines candidate references and idea/claim leads out of extracted source text into per-source lead tables, then consolidates many sources' lead tables into deduplicated, cross-source-ranked follow-up tables (reference_leads.csv, hypothesis_leads.csv) and a prioritized shortlist. Invoke when a research or literature-review project has new extracted-text sources to sweep for follow-up leads, or when scattered per-source lead CSVs need merging into one ranked, deduplicated view.
---

# Citation Lead Mining and Dedup

## What this skill produces

Two kinds of output, at two stages:

**Stage 1 (mine, per source):** for one source's extracted text, a
`refs_<slug>.csv` of candidate reference leads and an `ideas_<slug>.csv` of
candidate idea/claim leads.

**Stage 2 (consolidate, across sources):** merging every `refs_*.csv` and
`ideas_*.csv` in a leads directory into `reference_leads.csv` and
`hypothesis_leads.csv` — deduplicated, with a count of how many independent
sources raised each lead — plus `shortlist.md`, a prioritized follow-up list
grouped by theme with a "Gaps" section naming thin-coverage themes.

## When to use this skill

- A research/literature-review/citation-graph project has just extracted
  plain text from one or more new source documents, and needs to sweep them
  for references worth acquiring and ideas worth tracking as hypothesis
  leads — without re-reading sources already swept.
- Several sources have already been mined into per-source CSVs and now need
  merging into one deduplicated, ranked view (e.g. before compiling an
  acquisition list, or before deciding where a literature review is thin).
- A downstream process needs to know which candidate references are
  corroborated by multiple independent sources (a decent proxy for
  "probably worth acquiring first") versus mentioned by only one.

Do **not** use this skill to produce a citable bibliography directly. Its
output is explicitly unverified leads — see "The core discipline" below.

## The core discipline: leads, not citations

Every row this skill produces is a **candidate**, not a fact. A mined
"reference lead" means only: some source text, matched against a regex or
transcribed by hand, appears to point at a work with roughly this
author/year/title. It has not been confirmed to exist, confirmed to match
this printed metadata, or read for relevance.

Carry that status all the way through:
- Never promote a row from `reference_leads.csv` into a manuscript's
  bibliography, a claim ledger, or any citable location without first (a)
  confirming the work exists under this or a corrected identity, (b)
  confirming the printed metadata (author/year/title/venue), and (c)
  reading enough of it to confirm it actually supports whatever it will be
  cited for.
- `shortlist.md` stamps every entry `UNVERIFIED` for this reason. Leave that
  stamp in place until a human or a separate verification pass clears it.
- Never fabricate a reference or idea lead that doesn't trace to something
  actually present in the source text. If a source doesn't yield much,
  reporting a short/empty lead file is correct; padding it is not.

## Stage 1: mining one source

### Step 1a — mine reference leads (mechanical, scriptable)

Reference-list and in-text citations are mined by regex from the source's
extracted plain text — no judgement calls, fully automatable:

```
python scripts/mine_leads.py --mode citations \
  --source-slug <short-stable-slug> \
  --input path/to/extracted_text/<slug>.txt \
  --out-dir path/to/leads \
  --theme <theme-tag-for-this-source>
```

This runs two independent passes and concatenates their output into one
`refs_<slug>.csv`:

1. **Reference-list pass.** Finds the first heading in
   `--references-heading` (default tries "References", "Works Cited",
   "Bibliography" in order) and parses everything after it. Two
   sub-strategies, tried in order:
   - *Anchored* (default, high precision): treats each physical line that
     starts with `Author (Year).` as one reference. Works when the text
     extractor kept one reference per line.
   - *Paragraph-accumulation* (automatic fallback): if the anchored pass
     finds fewer than `--min-anchored-hits` references, instead treats each
     blank-line-separated block of text as one reference, handling
     extractors that wrap a single reference across multiple lines.

   Rows from this pass get `where_in_source=references_list`,
   `completeness=full_citation` (a full printed reference was captured,
   even though it's still unverified), and an empty `cited_title` — the
   regex extracts authors and year reliably but not title, so title stays
   for a human/agent to fill in during verification, not for the miner to
   guess.

2. **Body-citation pass.** Scans the *entire* text (not just the reference
   list) for narrative citations like `Smith (2001)` or
   `Smith & Jones (2004, 2006)`, capturing ~50 characters before and ~150
   after as `identifier_as_printed` context (tune with `--context-before` /
   `--context-after`). These rows get `completeness=partial_citation`
   because only a surname and year were captured — genuinely useful as
   leads (a source discussed this work enough to name-check it inline) but
   less complete than a reference-list hit. Skip this pass with
   `--skip-body-citations` if the source has no reliable in-text citation
   style (e.g. footnote-numbered sources).

Both passes deduplicate *within* the single source by (authors, year), so a
work cited five times in one article's body text yields one row, not five.

**When the regex approach breaks down.** Some source texts have citation
formatting too irregular for reliable regex extraction — footnote-numbered
systems, non-Latin scripts, heavily OCR-garbled reference lists, or
citation styles the two passes above don't anticipate. When that happens,
don't fight the regex: hand-transcribe the reference list directly into a
CSV matching the `refs_<slug>.csv` schema (see field list below) and skip
the citations mode entirely for that source. Coverage and correctness beat
forcing an automated path that will silently mis-parse a mangled source.
This manual-transcription fallback is a normal, expected part of the
workflow, not a failure state.

### Step 1b — mine idea/claim leads (requires reading, not scriptable)

Identifying a source's important ideas and claims requires actually reading
and understanding the text — there is no reliable regex for "what is this
source's main contribution." That step is the reading agent's job, not the
script's. The script's job is only to take what the agent already
identified and normalize it into the standard CSV schema, validating that
required fields are present.

Workflow:

1. Read the source (or the relevant portion of it).
2. Identify a small number of **specific, checkable** idea/claim leads —
   not vague theme labels. A good idea lead names a concrete claim and
   anchors it to a locatable place in the source (a section heading, a page
   range, "Abstract, second paragraph"), so a later reader can go find it
   and check whether the source actually says that. "This article discusses
   information systems" is not a usable idea lead; "this article claims
   that decomposing documents into standardized units enables reordering
   independent of the original authorial structure, stated in the section
   on X" is.
3. Write those ideas to a small JSON file, one object per idea:

   ```json
   [
     {
       "idea": "Specific, checkable claim text.",
       "where_stated": "Section heading or locator within the source.",
       "theme": "optional-theme-tag",
       "priority": 1,
       "suggested_search_targets": "optional: what a follow-up search should look for"
     }
   ]
   ```

   Only `idea` and `where_stated` are required; rows missing either are
   skipped (with a warning) rather than silently written incomplete.

4. Normalize it into `ideas_<slug>.csv`:

   ```
   python scripts/mine_leads.py --mode ideas \
     --source-slug <short-stable-slug> \
     --ideas-input path/to/<slug>.ideas.json \
     --out-dir path/to/leads \
     --theme <default-theme-if-entry-omits-one>
   ```

Run both steps for a source in one call with `--mode both` (pass both
`--input` and `--ideas-input`).

### Reference lead CSV schema (`refs_<slug>.csv`)

`source_slug, cited_title, cited_authors, cited_year, cited_venue, identifier_as_printed, lead_type, theme, where_in_source, completeness`

### Idea lead CSV schema (`ideas_<slug>.csv`)

`source_slug, idea, where_stated, theme, priority, suggested_search_targets`

Hand-transcribed fallback rows must use these exact column names so Stage 2
can read them like any script-produced file.

## Stage 2: consolidating across sources

Once every source in the batch has a `refs_<slug>.csv` and/or
`ideas_<slug>.csv` in one directory, merge them:

```
python scripts/consolidate_leads.py \
  --leads-dir path/to/leads \
  --output-dir path/to/consolidated \
  --min-citations-for-shortlist 2 \
  --shortlist-size 25 \
  --sparse-theme-threshold 3
```

### Deduplication logic

Titles, when present, are normalized before comparison (Unicode NFD
normalize, lowercase, strip punctuation, collapse whitespace) so that
"The Origins of Order" and "the origins of order." collide to the same key.

The dedup key for a reference lead is chosen from the first available of,
in order:

1. `(normalized title, year)` — most specific, used when a title was
   captured.
2. `(normalized authors, year)` — used when no title was captured (the
   common case for body-citation leads, which only ever have a surname).
3. `(normalized identifier_as_printed, year)` — last resort, so a lead with
   neither a usable title nor a parseable author string still gets a key
   instead of being silently dropped.

This fallback chain matters: a naive dedup keyed only on title would drop
every body-citation lead that lacks one, discarding real signal. Idea leads
dedup on exact normalized idea text — deliberately conservative, since
merging two non-identical claims as "the same idea" loses information a
title/year merge does not.

### Cross-source ranking

Each unique reference lead accumulates the list of source slugs that
produced it (`cited_by_slugs`) and a count (`cited_by_count`). Sort
`reference_leads.csv` descending by `cited_by_count` — leads independently
corroborated by more sources are the better bet for acquisition priority.
`hypothesis_leads.csv` sorts by `priority` ascending, with the analogous
`raised_by_slugs` column (non-numeric or missing priority sorts last).

### Shortlist and gaps

`shortlist.md` pulls every reference lead with `cited_by_count >=
--min-citations-for-shortlist` (default 2 — i.e. corroborated by at least
one source beyond the first), caps the list at `--shortlist-size`, and
groups entries by theme. Every entry keeps the `UNVERIFIED` stamp described
above. It also lists themes whose *total* lead count (not just shortlisted
count) is at or below `--sparse-theme-threshold` under a "Gaps" heading —
a signal that a theme needs a fresh, targeted search rather than more
mining, since mining can only surface what the existing corpus already
mentions.

## End-to-end sequence

1. For each new source's extracted text: run `mine_leads.py --mode
   citations` (mechanical), then read the source and run `mine_leads.py
   --mode ideas` (requires judgement) — or `--mode both` for one call.
2. Repeat for every source in the batch, accumulating `refs_*.csv` /
   `ideas_*.csv` in one leads directory.
3. Run `consolidate_leads.py` once over that whole directory.
4. Read `shortlist.md`'s Gaps section to decide where a fresh literature
   search (not more mining) is needed.
5. Treat every row in every output file as UNVERIFIED until a separate
   verification pass confirms it — this skill's job ends at producing
   good candidates, not at certifying them.

## Worked example

See `examples/` for two tiny synthetic sources (clearly labeled fictional —
do not treat any name or claim in them as real) and the leads/consolidated
output produced by running both stages end to end. It demonstrates: a
reference lead corroborated across both synthetic sources rising to the
shortlist, an idea lead that two sources raised in identical wording
merging into one `hypothesis_leads.csv` row, and a thin-coverage theme
appearing in the Gaps section.
