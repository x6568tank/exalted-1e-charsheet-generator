# Transcription instructions

You are transcribing a scanned page from a tabletop RPG rulebook into Markdown.
Your output is copied directly into a file. Follow these rules exactly.

## Rule 0 — the one that matters most

**Transcribe what is printed. Never supply anything from your own knowledge.**

This is Exalted **First Edition**. Second Edition is a different game with
different numbers, and you have seen far more of it. If a number on this page
looks wrong to you, it is not wrong — you are reading First Edition. Copy it.

**If you cannot read a character with certainty, write `???` in its place.**

- `Minimum Melee: ???`
- `Cost: ??? motes`
- `Prerequisite Charms: Fists of ??? Technique`

A `???` costs the reader five seconds. A confidently wrong number can survive
for months undetected. Guessing is the worst thing you can do here. Never
average, never infer from a nearby entry, never "correct" anything.

## Rule 1 — do not interpret

- Do not summarise, shorten, paraphrase, or improve the wording.
- Do not fix spelling, grammar, or punctuation.
- Do not reorder anything.
- Do not add commentary, notes, or explanation inside the transcription.
- Do not convert anything to JSON or any other structured format.

## Rule 2 — output format

Start the output with the page number, as an HTML comment:

```
<!--PAGE 91-->
```

Then transcribe top to bottom, left column fully, then right column fully.
**Never interleave columns.** If you cannot tell where a column starts or ends,
say so in the report (see Rule 5) rather than guessing at the reading order.

Formatting map:

| On the page | In your output |
|---|---|
| Large chapter/section heading | `# HEADING` |
| Sub-heading | `## SUB-HEADING` |
| An entry title in ALL CAPS | `### ENTRY TITLE` |
| A stat line (`Cost:`, `Duration:`, `Type:`, `Minimum …:`, `Prerequisite Charms:`) | one line, verbatim, on its own line |
| Body paragraph | plain text, blank line between paragraphs |
| Bulleted item | `- ` prefix |
| Italic quote or epigraph | `> ` prefix |

Keep the book's own curly quotes (’ “ ”), em dashes (—) and accents. Do **not**
convert them to ASCII.

**Expand ligatures.** The scan may render `ﬁ ﬂ ﬀ ﬃ ﬄ` as single glyphs; write
them as `fi fl ff ffi ffl`. This is the only change to the text you may make.

## Rule 3 — stat lines are the high-risk zone

The lines that begin `Cost:`, `Type:`, `Duration:`, `Minimum <something>:` and
`Prerequisite Charms:` are the whole reason this transcription exists. Slow down
on them.

- Copy each one **exactly**, including the words after the number
  (`3 motes, 1 Willpower`, `1 mote per die`, `None`, `Permanent`).
- Every digit you are not fully certain of becomes `???`.
- `l` vs `1`, `S` vs `5`, `O` vs `0`, `6` vs `8`: if the glyph is ambiguous at
  the resolution you were given, that is a `???`.
- If a stat line is present on the page but you cannot see it at all, write the
  label with `???` rather than omitting the line.

## Rule 3b — spell pages

A spell page works the same way, with two differences.

**Spells have fewer stat lines.** Usually only `Cost:`. If the entry prints
others (`Duration:`, `Target:`, `Type:`), transcribe them anyway, each on its own
line — do not drop one because spells "normally" lack it.

**The section heading is load-bearing.** Spells are grouped under headings that
name their circle:

```
## SPELLS OF THE TERRESTRIAL CIRCLE
## THE CELESTIAL CIRCLE
## NECROMANCY OF THE SHADOWLANDS CIRCLE
```

Transcribe every such heading as a `##` line, exactly where it appears. It is
what assigns each following spell to its circle, so a dropped heading silently
files spells under the wrong one.

The circles are: Terrestrial, Celestial, Solar (sorcery); Shadowlands,
Labyrinth, Void (necromancy); Man-Machine, God-Machine (Alchemical weaving).

If the page's spells sit under a heading printed on an **earlier** page you were
not shown, do not guess which circle they belong to. Transcribe the entries and
say so under `MISSING`:

```
MISSING:
- no circle heading on this page; the spells continue a section that began earlier
```

## Rule 4 — things you must NOT transcribe

- **Diagrams, flowcharts, and boxes-and-arrows trees.** If the page has one,
  write `<!--DIAGRAM: not transcribed-->` where it appears and move on. Do not
  attempt to describe the connections between boxes.
- Page furniture: running headers, footers, page numbers in the margin,
  decorative borders, chapter tabs.
- Illustration captions, unless the caption is body text.

Sidebars and inset boxes **are** transcribed — mark one with a `## SIDEBAR: <its
title>` heading so it is not mistaken for body text.

## Rule 5 — the report

After the transcription, output a `---` separator, then a short report:

```
---
UNCERTAIN:
- line "Minimum Melee: ???" — glyph unreadable, could be 3 or 8
- entry title on the right column, third heading — partly cut off

MISSING:
- a Duration: line appears to be absent for "Ghost Step Method"

NOT TRANSCRIBED:
- diagram, upper right
```

Any of the three sections may say `none`. Listing an uncertainty is a successful
outcome, not a failure — it is the most useful thing in your output.

## Rule 6 — scope

Transcribe only the image you were given. Do not continue an entry that runs off
the bottom of the page; stop where the page stops and note it under `MISSING`.
Do not produce output for a page you were not shown.
