"""Phase 5: commentary-to-event alignment audit. Research-only; NOT a live model. Splits are
match-level/competition-level ONLY. Runs on SYNTHETIC aligned data when no permitted real sample exists."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary.alignment import align_confidence, classify_alignment

# synthetic (commentary_event_type, comm_team, comm_min, true_event_type, true_team, true_min)
SYNTH = [
 ("goal","H",23,"goal","H",23), ("yellow_card","A",41,"yellow_card","A",42),
 ("substitution","H",60,"substitution","H",61), ("goal","A",75,"shot","A",75),
 ("corner","H",10,"corner","H",10), ("red_card","A",88,"foul","A",88),
]

def main():
    rows=[(align_confidence(*s[:3], *s[3:]), s) for s in SYNTH]
    tp=sum(1 for c,s in rows if c>=0.75 and s[0]==s[3])
    pred_pos=sum(1 for c,_ in rows if c>=0.75); actual_pos=sum(1 for s in SYNTH if True)
    prec=tp/pred_pos if pred_pos else 0; rec=tp/sum(1 for s in SYNTH if s[0]==s[3])
    f1=2*prec*rec/(prec+rec) if (prec+rec) else 0
    print("SYNTHETIC alignment demo (real run pending permitted commentary):")
    for c,s in rows: print(f"  conf={c:.2f} class={classify_alignment(c)} | {s}")
    print(f"precision={prec:.2f} recall={rec:.2f} f1={f1:.2f}")
    print("SPLIT RULE: match-level/competition-level only (never random row split within a match).")

if __name__ == "__main__":
    main()
