# Obsidian vault — schema + rules

You are operating inside an Obsidian vault that follows the llm-wiki methodology. This file defines the vault's structure and your obligations as a knowledge contributor.

## Three-layer architecture

```
vault/
├── .raw/       Layer 1 — immutable source documents (transcripts, PDFs, pastes)
├── wiki/       Layer 2 — LLM-curated knowledge base
├── projects/   Layer 3 — per-channel project workspaces
└── CLAUDE.md   this file
```

`.raw/` is dot-prefixed so Obsidian hides it from the file explorer and graph.

## wiki/ subfolders

| Folder | Contents |
|---|---|
| `index.md` | Master catalog of all wiki pages |
| `log.md` | Chronological record of operations (ingests, fold-merges, lints) |
| `hot.md` | ~500-word summary of recent context. Updated frequently. |
| `overview.md` | Executive summary of the whole wiki |
| `sources/` | One summary page per `.raw/` source |
| `entities/` | People, orgs, products, repos. One file per entity. |
| `concepts/` | Ideas, patterns, frameworks. One file per concept. |
| `domains/` | Top-level topic areas. |
| `comparisons/` | Side-by-side analyses |
| `questions/` | Filed answers to user queries |
| `meta/` | Dashboards, lint reports, conventions |

## projects/ subfolders

One folder per Discord channel, named with the channel's slug.

```
projects/
├── {channel-slug}/
│   ├── plan.md         current plan + status
│   ├── decisions.md    design decisions with reasoning
│   ├── notes.md        channel-specific scratch
│   └── *.md            other project-specific docs
```

Cross-project knowledge **does not live here.** It lives in `wiki/`. If something would be useful to a different channel later, write it there.

## Hot cache

`wiki/hot.md` is a ~500-word summary of recent context. Every session reads it first to get oriented. Update it:
- After every ingest
- After significant query exchanges
- At the end of every session

Format:
```markdown
---
type: meta
title: "Hot Cache"
updated: YYYY-MM-DDTHH:MM:SS
---

# Recent Context

## Last Updated
YYYY-MM-DD. [what happened]

## Key Recent Facts
- ...

## Open Threads
- ...
```

## Page conventions

Every wiki page has frontmatter:
```yaml
---
type: entity | concept | domain | source | comparison | question | meta
title: "Page Title"
created: YYYY-MM-DD
updated: YYYY-MM-DDTHH:MM:SS
tags: [tag1, tag2]
aliases: [alt-name]
---
```

Cross-reference liberally with `[[wiki-link]]` syntax. Forward references to pages that don't exist yet are fine — they mark something worth writing later.

## Workflow obligations

1. **Before deriving anything non-trivial, query `wiki/` first.** You may already have the answer.
2. **When you learn something cross-project**, file it in `wiki/` immediately, not "later".
3. **Update `hot.md`** at meaningful checkpoints.
4. **Log significant operations** in `log.md`.
5. **Run `wiki-lint` periodically** to catch contradictions and orphans.

The wiki is the product. Chat is just the interface.
