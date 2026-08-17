# Citation Lead Mining and Dedup

Turn extracted source text into candidate references and idea leads, then
merge many sources' leads into deduplicated, cross-source-ranked follow-up
tables and a prioritized shortlist.

## What it does

If you're running a literature review, a citation-graph build, or any
research project that works from a pile of extracted source texts, this
skill covers the "what should I look at next" step:

1. **Mine** each source text for two kinds of leads:
   - *Reference leads* — works the source cites, pulled from its reference
     list and its in-text citations.
   - *Idea leads* — specific, checkable claims worth tracking as follow-up
     hypotheses, identified by actually reading the source.
2. **Consolidate** every source's leads into one deduplicated view:
   - `reference_leads.csv`, ranked by how many independent sources cite
     each work.
   - `hypothesis_leads.csv`, ranked by priority, showing which sources
     raised each idea.
   - `shortlist.md`, a prioritized, theme-grouped follow-up list with a
     "Gaps" section flagging themes that are thin on leads.

Every output row is explicitly marked as an unverified candidate. This
tool finds leads worth checking — it does not check them, and nothing it
produces should be cited anywhere without a separate verification pass.

It is domain-agnostic: the worked example below uses a scholarly-research
framing (mining a literature corpus for citation leads), but the same
mine-then-consolidate-then-dedup pattern applies to any pile of text
documents you need to sweep for candidate follow-ups and cross-document
corroboration.

## Installation

This is an [Agent Skill](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
following the portable `SKILL.md` convention. To install it:

- **Claude Code:** copy this folder into `.claude/skills/citation-lead-mining-and-dedup/`
  in your project (or into your user-level skills directory to make it
  available across projects).
- **Any other agent runtime that supports the `SKILL.md` convention:** copy
  this folder into that runtime's equivalent skills directory. The
  `SKILL.md` frontmatter (`name`, `description`) and body are
  runtime-agnostic.

The bundled scripts also run standalone with no framework at all — see
below.

## Worked example (synthetic data)

`examples/` contains two tiny, clearly fictional source texts and the
idea-lead files an agent would draft for them, plus the leads and
consolidated output produced by running the full pipeline. Nothing in
`examples/` is real — every name, title, and claim is a placeholder built
to exercise the pipeline (cross-source citation dedup, cross-source idea
dedup, and the sparse-theme gap report).

Reproduce it yourself:

```bash
# Stage 1: mine each source
python scripts/mine_leads.py --mode both \
  --source-slug synthetic-source-a \
  --input examples/source_text/synthetic-source-a.txt \
  --ideas-input examples/ideas/synthetic-source-a.ideas.json \
  --out-dir examples/leads \
  --theme indexing-history

python scripts/mine_leads.py --mode both \
  --source-slug synthetic-source-b \
  --input examples/source_text/synthetic-source-b.txt \
  --ideas-input examples/ideas/synthetic-source-b.ideas.json \
  --out-dir examples/leads \
  --theme retrieval-order

# Stage 2: consolidate across both sources
python scripts/consolidate_leads.py \
  --leads-dir examples/leads \
  --output-dir examples/consolidated
```

Result: `examples/consolidated/reference_leads.csv` shows the "Vantree,
R. (2001)" lead with `cited_by_count=2` (mined independently out of both
synthetic sources), `hypothesis_leads.csv` shows the identical-wording idea
lead merged with `raised_by_slugs=synthetic-source-a;synthetic-source-b`,
and `shortlist.md` lists it under the "Indexing History" theme while
flagging "Retrieval Order" under Gaps (only two total leads).

## Standalone CLI usage

Both scripts are plain Python 3 standard-library scripts — no
dependencies to install.

```bash
python scripts/mine_leads.py --help
python scripts/consolidate_leads.py --help
```

Typical real usage, run once per source and then once total:

```bash
# Per source, repeated for every extracted-text file you have:
python scripts/mine_leads.py --mode citations \
  --source-slug my-source-2024 \
  --input path/to/extracted_text/my-source-2024.txt \
  --out-dir path/to/leads

# (read the source, draft path/to/ideas/my-source-2024.json by hand, then:)
python scripts/mine_leads.py --mode ideas \
  --source-slug my-source-2024 \
  --ideas-input path/to/ideas/my-source-2024.json \
  --out-dir path/to/leads

# Once, after every source in the batch has been mined:
python scripts/consolidate_leads.py \
  --leads-dir path/to/leads \
  --output-dir path/to/consolidated
```

All paths are passed as arguments; nothing is hard-coded to a particular
project layout. See `SKILL.md` for the full methodology, CSV schemas, and
the reasoning behind the dedup key fallback chain and the shortlist/gaps
logic.

## License

MIT — see `LICENSE`.
