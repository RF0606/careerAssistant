# Fictional examples

All examples are fictional. They are not default user facts or live jobs.
Generate a separate demonstration workspace with:

```text
python tests/fixtures.py <temporary-workspace> --persona operations --compile
python tests/fixtures.py <another-temporary-workspace> --persona software --projects --compile
```

The script writes a sample source, confirmed test facts, preferences, role skill,
assessment and draft. Without --compile it needs no PDF tools. Generated data stays
in the chosen workspace, not this folder. Use it only for demonstrations/testing;
ordinary user onboarding gathers that user's actual sources and confirmations.
