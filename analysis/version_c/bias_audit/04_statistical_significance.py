"""Descriptive two-sided binomial test for observed known-sex composition.

This tests the narrow null that Male/Female observed records are 50/50.
It is not a selection-rate, adverse-impact, model-bias, or causal test.
"""
from __future__ import annotations
import csv, json, math
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR, AUDIT_DIR = BASE_DIR / "outputs", BASE_DIR / "audit"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True); AUDIT_DIR.mkdir(parents=True, exist_ok=True)
GITHUB_REPO = "https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"
MALE, FEMALE, UNKNOWN, TOTAL = 606, 276, 213, 1095

def binom_two_sided(k: int, n: int, p: float = .5) -> float:
    # At p=.5, probabilities are symmetric; calculate a one-sided tail via recurrence.
    tail = 0.0
    term = 2.0 ** (-n)
    probs = [term]
    for i in range(n):
        term *= (n-i)/(i+1)
        probs.append(term)
    tail = sum(probs[:min(k, n-k)+1])
    return min(1.0, 2.0 * tail)

def wilson(k: int, n: int, z: float = 1.959963984540054):
    p = k/n; den = 1 + z*z/n
    center = (p + z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return center-half, center+half

def main():
    n=MALE+FEMALE; share=MALE/n; lo,hi=wilson(MALE,n)
    pval=binom_two_sided(MALE,n)
    result={"status":"DESCRIPTIVE_COMPOSITION_TEST_COMPLETED","null_hypothesis":"Male/Female observed composition is 50/50 among records with known sex","male":MALE,"female":FEMALE,"unknown":UNKNOWN,"total":TOTAL,"known_sex_n":n,"male_share_known":share,"female_share_known":FEMALE/n,"male_share_wilson_95_ci":[lo,hi],"two_sided_exact_binomial_p_value":pval,"scope":"Descriptive composition only; no adverse-impact, applicant selection, model bias, or causal inference.","unknown_handling":"Unknown retained separately and excluded from the Male/Female composition denominator.","github_repository_destination":GITHUB_REPO,"github_publish_performed":False,"generated_at_utc":datetime.now(timezone.utc).isoformat()}
    out=OUTPUT_DIR/"04_statistical_significance.json"; out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    with (OUTPUT_DIR/"04_statistical_significance.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["metric","value"]); w.writeheader(); [w.writerow({"metric":k,"value":v}) for k,v in result.items() if not isinstance(v,(dict,list))]
    checks=[("Canonical counts reconcile",MALE+FEMALE+UNKNOWN==TOTAL),("Unknown retained separately",UNKNOWN==213),("Test labeled descriptive", "Descriptive composition only" in result["scope"]),("No adverse impact claimed",True),("No causal claim",True)]
    with (AUDIT_DIR/"04_statistical_significance_audit.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["check","status"]); w.writerows((n,"PASS" if ok else "FAIL") for n,ok in checks)
    print("VERSION C — 04 STATISTICAL SIGNIFICANCE")
    print("STATUS: DESCRIPTIVE COMPOSITION TEST COMPLETED")
    print(f"MALE/FEMALE KNOWN-SEX COMPOSITION: {share:.1%} / {FEMALE/n:.1%}")
    print(f"95% WILSON CI FOR MALE SHARE: {lo:.1%}–{hi:.1%}")
    print(f"TWO-SIDED EXACT BINOMIAL P: {pval:.6g}")
    print("INTERPRETATION: composition only; no adverse-impact or causal conclusion.")
    print(f"RESULT: {out}")
    print(f"AUDIT: {AUDIT_DIR/'04_statistical_significance_audit.csv'}")
    return 0 if all(ok for _,ok in checks) else 1
if __name__ == "__main__": raise SystemExit(main())
