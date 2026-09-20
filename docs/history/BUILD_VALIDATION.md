# Build Validation

Validated locally for this package revision:

```text
pytest -q  -> 27 passed
wcdrawlab inplay -> executed successfully
wcdrawlab validate-source -> approved an allowlisted URL and rejects unapproved domains in tests
python -m compileall -q src -> passed
```

No live provider or Kalshi order was called during validation. The package ships in
paper-first mode and contains no API credentials.
