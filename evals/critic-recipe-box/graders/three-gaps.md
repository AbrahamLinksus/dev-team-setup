---
type: llm
focus: trace
weight: 3
---

Read the product-critic's REPORT and Gaps section as shown in the run (and docs/scenarios.md if
the trace shows it).

PASS only if the critic raised all three of these as gaps (any wording, any severity):
1. **Range or vague amounts**: ingredients like "1-2 cloves", "a pinch" or "salt to taste" that
   the amount/unit/name format can't hold or can't scale.
2. **Awkward fractions when scaling**: scaling produces amounts like 0.333 cup or 1.5 eggs, and
   the spec doesn't say how they are rounded or shown (⅓, ½, whole eggs).
3. **No backup / data loss**: recipes live only on one phone, so losing, wiping or replacing it
   loses every recipe, and the spec never says what happens then.

FAIL if any of the three is missing, or if the critic edited docs/SPEC.md. Name which are missing.
