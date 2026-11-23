# Citation lead mining and dedup (paste into ChatGPT, Claude.ai, Gemini or a local model)

You are helping with a literature review. I will paste extracted text from one or more sources. Produce unverified follow-up leads and merge them across sources.

## Step 1: per source
For each source, give me two tables.

Reference leads: works the source cites, taken from its reference list and in-text citations. Columns: source_slug, cited_title, cited_authors, cited_year, cited_venue, identifier_as_printed (DOI or similar exactly as printed), lead_type (reference_list or in_text), theme, where_in_source, completeness (complete or partial). Copy only what is in the text. Leave a field empty rather than guessing. Never invent a reference.

Idea leads: specific, checkable claims worth following up as hypotheses. Columns: source_slug, idea, where_stated (section or a short exact quote), theme, priority (high, medium, low), suggested_search_targets.

Treat every row as an unverified candidate.

## Step 2: merge
When I say "consolidate", combine all tables so far:
1. Reference leads: treat entries as the same work when the DOI matches; otherwise when first-author surname, year and normalized title match. List each work once with cited_by_count (number of different sources citing it) and the source slugs. Sort by cited_by_count, highest first.
2. Idea leads: merge ideas with the same meaning. Show raised_by_slugs and the highest priority. Sort by priority.
3. Shortlist: group the top items by theme as a prioritized to-do list. Add a "Gaps" section naming themes with three or fewer leads.

## Rules
- Every row stays "unverified candidate". Say plainly that nothing here may be cited before it is checked against the real work.
- Do not add details that are not in the text I gave you.
- If a source text is too long, ask me to send it in parts.

Start by asking me for the first source text and its short slug.
