# Clue annotation schema

One JSON object per clue. The analysis is the whole point of the corpus: the
answer is already known from the published solution, so what is being recorded
is *how the clue works*.

```json
{
  "id": "20260725-8A",
  "definition": "Sky feature",
  "devices": ["charade"],
  "indicators": [{"text": "visiting", "type": "insertion"}],
  "fodder": "RA + IN + BOW",
  "substitutions": [
    {"surface": "artist",       "letters": "RA",  "kind": "abbreviation"},
    {"surface": "the East End", "letters": "BOW", "kind": "place"}
  ],
  "explanation": "RA (artist) + IN (visiting) + BOW (a district of London's East End)."
}
```

## Fields

- **definition** — the exact words of the clue that define the answer, copied
  verbatim from the clue.
- **devices** — one or more of: `anagram`, `charade`, `container`, `hidden`,
  `reversal`, `deletion`, `homophone`, `substitution`, `selection` (first/last/
  alternate letters), `double-definition`, `cryptic-definition`, `&lit`,
  `spoonerism`.
- **indicators** — the words doing the signalling, each tagged with the device
  it signals. Types: `anagram`, `container`, `insertion`, `reversal`, `hidden`,
  `deletion`, `homophone`, `selection`, `link`. Omit words that are merely
  surface reading.
- **fodder** — the raw material the wordplay operates on, written as the setter
  assembles it (`RA + IN + BOW`, or the letters of an anagram).
- **substitutions** — the heart of the database. Every point where a word or
  phrase in the clue stands for specific letters. Record the surface word as it
  appears and the letters it yields.
  - `kind` is one of: `abbreviation` (artist → RA), `single-letter`
    (energy → E), `nato` (I → INDIA), `roman` (fifty → L), `cricket`
    (maiden → M, caught → C), `music` (note → A–G, quiet → P),
    `chess`, `chemical` (gold → AU), `place` (the East End → BOW),
    `synonym` (a plain word-for-word swap that the wordplay relies on),
    `foreign` (the French → LE), `other`.
  - Record it even when it is obvious — the frequency counts are the output.
- **explanation** — one or two sentences showing the letters coming together.

## Rules

- Copy `definition` verbatim from the clue text; do not paraphrase it.
- Do not invent substitutions that the wordplay does not use.
- If a clue is a double definition or cryptic definition with no wordplay
  machinery, leave `indicators`, `fodder` and `substitutions` empty and say so
  in the explanation.
- Where the parsing is genuinely uncertain, still give the best reading and add
  `"uncertain": true`.
