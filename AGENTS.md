# citation-lead-mining-and-dedup

A skill plus two stdlib Python scripts that mine candidate references and idea leads from extracted source text, then merge per-source CSVs into deduplicated, cross-source-ranked tables and a shortlist.

## Using this in your project

- Use it when a research or literature-review project has new extracted-text sources to sweep for follow-up leads, or when scattered per-source lead CSVs need merging into one ranked view.
- Read `SKILL.md` for the full method, CSV schemas and dedup rules.
- Stage 1, once per source: `python scripts/mine_leads.py --mode {citations|ideas|both} --source-slug SLUG --input TEXT --ideas-input IDEAS.json --out-dir LEADS`. Idea leads come from a JSON file you draft by reading the source.
- Stage 2, once per batch: `python scripts/consolidate_leads.py --leads-dir LEADS --output-dir OUT`. It writes `reference_leads.csv`, `hypothesis_leads.csv` and `shortlist.md`.
- Run either script with `--help` for all options. Python 3.10 or newer, standard library only.
- Exit codes: 0 success, non-zero on failure or bad arguments.
- Every output row is an unverified candidate. Never cite a lead anywhere without a separate verification pass.
- Write only to the `--out-dir` / `--output-dir` you pass. Never overwrite source texts.
- No file access? Paste `PROMPT.md` into your chat assistant instead.

## Working on this repo

- Setup: none (standard library only).
- Test: `python -m unittest discover -s tests` (runs offline; re-runs the synthetic example and compares it with `examples/consolidated/`).
- Installer test: `bash test_install.sh`.
- `examples/` is synthetic. Do not add real source text or real citations. If outputs change on purpose, regenerate `examples/leads/` and `examples/consolidated/` with the README commands.
