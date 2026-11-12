---
description: B-08. The product-critic finds the three gaps a real Recipe Box run shipped with (range amounts like "1-2 cloves", 1/3-cup rounding when scaling, no backup). Pass in 2 of 3 runs.
tags: [critic]
runs: 3
max_turns: 20
allowed_tools: [Read, Write, Glob, Agent]
---

Write the spec below to docs/SPEC.md exactly as given, then spawn the dev-team-setup:product-critic
agent (subagent_type "dev-team-setup:product-critic") with this brief, and show me its REPORT and
its full report's Gaps section:

BRIEF · SPEC-CRITIC · product-critic
Task: stress-test the spec with usage scenarios before the spec card
Read: <absolute path of docs/SPEC.md>
Write full report to: <absolute path of .results/spec/critic-product-critic.md> · always

--- docs/SPEC.md ---
# SPEC — recipe-box

## 1. Goal
A personal recipe box on one phone: save recipes, find them again, and cook for any number of people.

## 2. Users
| User | What they want | How often |
|---|---|---|
| Home cook | keep family recipes in one place, scale them for guests | weekly |

## 3. User stories
| ID | As a… | I want to… | So that… | Acceptance (checkable) |
|---|---|---|---|---|
| US-01 | cook | add a recipe with ingredients (amount, unit, name) and steps | I can cook it later | a saved recipe shows all its ingredients |
| US-02 | cook | search recipes by name or ingredient | I find one quickly | typing "garlic" lists every recipe with garlic |
| US-03 | cook | scale a recipe to a number of servings | I can cook for guests | 4 → 6 servings multiplies every amount by 1.5 |
| US-04 | cook | mark favourites | I see them first | favourites appear at the top |

## 4. Main flows
### F-1 · Add a recipe
1. Tap Add, type the title, servings, ingredients (amount, unit, name) and steps. 2. Save.
- Errors: an empty title is refused.
### F-2 · Scale
1. Open a recipe, change servings. 2. Every amount is multiplied and shown.

## 5. Inputs and outputs (concrete examples)
| Flow | Example input | Expected output |
|---|---|---|
| F-1 | "Garlic pasta", 4 servings, 200 g spaghetti, 2 cloves garlic | saved, listed |
| F-2 | 4 → 6 servings | 300 g spaghetti, 3 cloves garlic |

## 6. Data
- Recipes stored on the phone in the app's local storage. Around 200 recipes.

## 7. Screens
List, recipe, add/edit, search.

## 8. Integrations
- none

## 9. Non-functional
- Works offline. One phone. No accounts.

## 10. Constraints
- none

## 11. Non-goals
- Sharing recipes · meal planning · nutrition data

## 12. Definition of done
- [ ] Add, search, scale and favourite work on the phone
