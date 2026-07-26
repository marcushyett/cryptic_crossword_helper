# Crux — deployable drill app

A static site. Two files, no build step, no dependencies.

```
index.html   the app
data.js      the drill deck, generated
```

## Deploying

Connect this directory to Vercel as the project root — framework preset
**Other**, no build command, output directory `.`. Pushes to the branch then
deploy automatically.

The MCP deploy route needs the `create project` permission on the Vercel
account; without it the API returns
`403 forbidden: You don't have permission to create a project`.

## Regenerating the deck

```bash
python scripts/build_web.py corpus/merged.jsonl web --examples 60
```

## What is in the deck, and why

Most cards carry **no clue text at all**. "What is *artist* worth?" and "what
does *about* signal?" are questions about conventions counted out of the
analysed corpus — derived facts, and the ones that repay drilling most. They are
also deduplicated, so you meet each convention once rather than once per clue
that happens to use it.

A small set of **worked examples** does quote clues, because you cannot tap the
definition without seeing the clue. Those are capped deliberately and credited
on the home screen: a teaching sample, not a copy of the puzzles. Raise
`--examples` only with that distinction in mind — this is a public, shareable
site, and the clues are a subscription product.

## Storage

Everything is `localStorage` under the key `crux-v1`: which cards have been
seen (so they do not repeat until the deck is exhausted), attempts, accuracy,
current and best run, and the day streak. No accounts, no server, no analytics.
Each friend gets their own progress on their own device.
