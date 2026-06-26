# Commentary Low-Confidence Signals — Build Report
Operationalizes the V2 decision-package recommendation ("retain corner/foul/yellow_card as flagged
low-confidence historical signals"). 0 silver classes were approved; this is the explicitly-flagged,
non-silver fallback product. Schema: schemas/commentary_low_confidence_signal_v1.yaml.
Built 2,710 flagged records (corner 1267, foul 1242, yellow_card 201); raw + processed gitignored; manifest
+ data card tracked; 5 synthetic tests; runtime/trading import-isolation enforced. Collector untouched.
