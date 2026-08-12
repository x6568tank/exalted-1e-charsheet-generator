# Brief — enforcing the Background numeric rules

**For a delegated authoring run (DeepSeek), code-reviewed afterwards.** Read
`docs/ARCHITECTURE.md`, `docs/status/backgrounds.md` and `docs/delegated-authoring.md`
first. Every ruling below came from the human on 2026-08-12 and is CLOSED — implement it
as written, do not re-derive it from the printed text, and do not extend it by analogy to
Backgrounds not named here.

Suite at the time of writing: **2,134 passing**.

## The situation

`BackgroundRule` already carries `min_rating`, `max_rating`, `requires`,
`requires_rating`, `dot_cost`, `expensive_above`, `expensive_dot_cost`,
`bp_surcharge_per_dot`, `budget_tiers`, `rating_per_dot`, `cap_pre_bp_exempt`. Several
splats already use them (Mountain Folk Backing ≤2, Dragon-Kings Celestial Manse ≤2, Ghost
Ancestor Cult ≤1, God-Blooded Inheritance 1–5, Alchemical Class ≥3). They are read by
`validate.background_issues(budgets, backgrounds)`.

**That function is called from exactly one place: `validate_chargen`.** So every
Background cap in the build is chargen-only today. Post-lock the Advantages tab edits
ratings freely — no XP, no check — because Backgrounds change through the story, not by
purchase (`advancement.py` has no Background path at all, deliberately).

Five items follow. Four are rules; the fifth is the plumbing three of them need.

---

## R1 — Sidereal Connections, capped by the Attribute total

**Printed** (`background.connections-sidereal`): "You cannot manage more points of
Connections than the sum of your character's Physical, Social and Mental Attributes
combined; for starting characters this means the total number of dots in Connections may
not exceed 27, unless bonus points have been spent toward Attributes."

**Binds: CHARGEN ONLY** (human's ruling).

**Shape.** A new `BackgroundRule` field expressing "cap from a trait total" — the cap is
the character's summed Attribute dots, not a literal. Author the field so the DATA names
what is summed; do not hardcode "Attributes" in the engine, and do not write `27`
anywhere. 27 is what the sum happens to equal for a default Sidereal chargen spread, not
a rule.

⚠ **`background_issues(budgets, backgrounds)` cannot see the Attributes.** Widen the
signature rather than reaching around it. Follow the precedent in
`docs/status/merits-flaws.md`: `derive.soak`, `derive.willpower` and
`lifecycle.lock_chargen` take an **optional** extra argument so an omission is a silent
fallback rather than a TypeError at every call site. Same shape here.

## R2 — Sidereal Celestial Manse ≤3 without Storyteller permission

**Printed** (`background.celestial-manse-sidereal`): "Characters cannot buy above
Celestial Manse ••• without special Storyteller permission — more impressive digs are
reserved for higher-ranking individuals."

**Binds: BOTH SIDES OF THE LOCK** (human's ruling — the only rule in this brief that
does, alongside R4's lifted ceiling).

**Shape.** `max_rating: 3` on the Sidereal row, plus a **PER-CHARACTER** `HouseRules`
toggle that lifts it. `HouseRules` is the home for every Storyteller toggle; fields are
marked TABLE-WIDE or PER-CHARACTER **in comments only**, and a party-wide "apply to all"
control may only touch the table-wide ones — so the comment is load-bearing, write it.
Read it through a `validate.*` helper the way `validate.foreign_charms_permitted` is read;
no UI module learns the field name.

## R3 — Mortals may not purchase Artifact or Manse without Storyteller permission

**Printed** (Exalted core p.103, Step Four: Advantages —
`images/Mortals/Mortals & Heroic Mortals/Exalted p103.png`): "Mortals only receive 5 dots
for Backgrounds and may not purchase the Artifacts or Manse Backgrounds without
Storyteller permission; if a mortal has control over one of these, it's a plot device, not
an object for him to use."

**Binds: CHARGEN ONLY** (human's ruling — there is no post-lock purchase to bar).

**Shape.** The same construction as R2: a bar in data on the Mortal rows, lifted by a
**PER-CHARACTER** `HouseRules` toggle. It applies to both mortal origins (`heroic` and
`ordinary`) — one splat, two origins. Note this is a BAR (rating must be 0), not a
ceiling; if an existing field already expresses "may not take this at all", use it rather
than inventing a second way to say the same thing.

## R4 — Mountain Folk Artifact rises to 10

**Printed** (`background.artifact-mountainfolk`): "They pay only one Background or bonus
point to purchase each dot, even above a rating of 3. The greatest Enlightened heroes of
the Mountain Folk can possess this Background above a rating of 5 … with each dot beyond 5
costing one bonus point and granting an additional dot of total artifacts."

**Human's ruling 2026-08-12: the ceiling is 10.** The book does not print an upper bound;
10 is the human's call and is the number to author.

**Binds: BOTH SIDES** — a character who leaves chargen at 6 must still hold 6, and must be
able to reach 7 when the story grants one.

**Shape.** Ceiling 10 in data for both Mountain Folk origin rows, and one bonus point per
dot above 5. Half of this is already authored (`rating_per_dot: 2`, `cap_pre_bp_exempt:
true`), and `bp_surcharge_per_dot` already exists — check what the existing fields do
before adding one. **Do not raise anyone else's ceiling**: 5 stays the cap for every other
splat and every other Background.

## R5 — the plumbing R2 and R4 need

Two hardcoded `5`s make R4 unrecordable no matter what the data says:

1. `ui/advantages.py` `_chargen_backgrounds.cap_for` returns `min(meritsmod.DOT_MAX, …)`;
2. `ui/advantages.py:288` (the play regime) is `ui.number(value=…, min=0, max=5)`.

Both must take their ceiling from the same engine-side answer. The second is also game
logic living in a widget, which breaks the `ui → engine → models` rule — fixing it is part
of this job, not a follow-up.

And R2's post-lock half needs `background_issues` **called after the lock as well**. Find
where the post-lock validation runs and add the call there; do not duplicate the function.

⚠ Adding that second call site makes EVERY existing `max_rating` bind post-lock, which is
NOT what was ruled. Only R2 and R4 bind on both sides. Whatever mechanism you use — a
per-rule flag in data, or passing the phase in — the other splats' caps must keep behaving
exactly as they do today, and a test must pin that.

---

## Deliberately skipped — do not author these

- **Mountain Folk Backing ≤3 "for private organizations"** — a second, organisation-typed
  cap on the same Background. Human's ruling: SKIP. Narrative, not modellable.
- **"Non-ronin Sidereals do not generally start with Resources, using Salary instead"** —
  human's ruling: "do not generally" is a ruling, not a threshold. SKIP.

Both are recorded here so the next gap-diff does not report them as oversights. **"Missing
from the build" is not "should be authored."**

## Rules of the area

- **Thresholds are DATA on `BackgroundRule`; nothing splat-specific in code.**
  `engine/artifacts.py` is the precedent — read it first. No module may branch on a splat
  name or a Background id to decide a number.
- **Never author a printed value you have no page for.** Every value here has its source
  quoted above. If you need one that is not, STOP and flag it — do not supply it from
  general Exalted knowledge, and never from 2e.
- **1e only.** 2e is far better represented in training data; a 2e number will feel right
  and be wrong.
- **A field with a writer and no reader is this project's recurring bug** — four of them
  in the last delegated run. Every field you add must be read, and the read must run in
  the phase the rule binds in. A rule checked only in `validate_chargen` does nothing
  post-lock; that is the exact defect R2 exists to avoid.

## Tests required

Not "a test per field" — a test per **binding**:

1. R1: a Sidereal over the Attribute sum errors at chargen; one at exactly the sum does
   not; spending BP on Attributes raises the allowance. **Assert against a computed sum,
   never the literal 27.**
2. R2: over 3 errors at chargen AND post-lock; the per-character toggle lifts both; a
   second character at the same table is unaffected (it is PER-CHARACTER).
3. R3: a mortal with Artifact or Manse errors at chargen, in both origins; the toggle
   lifts it; a non-mortal is unaffected.
4. R4: a Mountain Folk character reaches 10 and is refused at 11; each dot above 5 costs
   one bonus point; **every other splat still stops at 5**.
5. R5: the chargen dot track offers 10 pips for a Mountain Folk Artifact row and 5 for a
   Solar one; the play number input accepts 7 for the former and refuses it for the
   latter. Drive these **through the UI harness** (`tests/_ui_main.py` routes) — the
   hardcoded ceilings are invisible to an engine-only test, which is why they survived
   this long.
6. R5: an existing chargen-only cap (Mountain Folk Backing ≤2, Unenlightened) still
   behaves as it does today after the post-lock call site is added.

Every new test must FAIL against the current code. State in the PR/summary which test
pins which ruling.

## Flag, do not decide

If any of these comes up, stop and write it in the summary rather than choosing:

- any value not quoted in this brief;
- whether a rule binds in a phase not stated here;
- anything requiring an XP price for a Background (there is none — Backgrounds are free
  story edits post-lock, and inventing a rate would be a house rule wearing a printed
  rule's clothes);
- any case where making R2/R4 bind post-lock would change another splat's behaviour.
