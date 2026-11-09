# Prompts · small benchmark

Both runs start in a folder that contains a copy of `spec.md`.

**Normal session** (plugin disabled):
```
Build the app described in spec.md in this folder. Work until every item in "Quality bar" is met, then stop and give me a short summary.
```

**Plugin session** (plugin enabled):
```
/setup-project Build the app described in spec.md in this folder. Treat spec.md as the full requirements and answer spec questions from it.
```
