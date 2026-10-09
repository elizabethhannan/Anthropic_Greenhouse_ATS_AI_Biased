"""Step 10 — build a self-contained final executive dashboard (inline SVG)."""
from __future__ import annotations
import html, json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/"outputs"
SOURCE=OUT/"09_executive_evidence_consolidation.json"
TARGET=OUT/"10_final_d3_executive_dashboard.html"
GITHUB="https://github.com/elizabethhannan/Anthropic_Greenhouse_ATS_AI_Biased"

def main():
    if not SOURCE.is_file(): raise SystemExit("Run 09_executive_evidence_consolidation.py first.")
    data=json.loads(SOURCE.read_text(encoding="utf-8"))
    counts=data["observed_outcomes"]; gaps=data.get("missing_audit_steps",[])
    pct=data["known_sex_percentages"]
    cards="".join(f'<div class="metric"><span>{k}</span><b>{v:,}</b></div>' for k,v in [("MALE",counts["MALE"]),("FEMALE",counts["FEMALE"]),("UNKNOWN",counts["UNKNOWN"])])
    gap_html=("<p class='gap'>Prior analysis artifacts not present: "+html.escape(", ".join(gaps))+"</p>" if gaps else "")
    findings=[]
    for item in data["evidence_layers"]:
        findings.append(f'<article><small>{html.escape(item["layer"])}</small><strong>{html.escape(item["status"])}</strong><p>{html.escape(item["finding"])}</p><em>{html.escape(item["limitation"])}</em></article>')
    document=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Version C executive evidence dashboard."><title>Version C — Employment Evidence Dashboard</title><style>
:root{{--navy:#12273a;--blue:#315f82;--teal:#16877e;--gold:#c18a31;--red:#9a4642;--cream:#f6f3eb;--white:#fff;--muted:#526576;--line:#dce3e7}}*{{box-sizing:border-box}}body{{margin:0;background:var(--cream);color:var(--navy);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}main{{max-width:1180px;margin:auto;padding:32px 24px 60px}}.top{{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap}}.tag{{font-size:.78rem;letter-spacing:.13em;text-transform:uppercase;color:var(--blue);font-weight:850}}.hold{{padding:7px 13px;border-radius:22px;background:#fff0d1;color:#644714;font-weight:800;font-size:.8rem}}h1{{font-size:clamp(2rem,4.2vw,3.5rem);line-height:1.08;letter-spacing:-.035em;margin:25px 0 14px}}h2{{font-size:1.2rem;margin:0 0 12px}}p{{color:var(--muted);margin:6px 0}}.thesis{{font-size:1.12rem;max-width:1040px}}.panel{{background:var(--white);border:1px solid var(--line);border-radius:17px;padding:23px;margin-top:20px;box-shadow:0 8px 24px #23394a10}}.summary{{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:center}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.metric{{padding:15px;background:#f8fafb;border:1px solid var(--line);border-radius:12px}}.metric span{{display:block;font-size:.73rem;color:var(--muted);font-weight:800;letter-spacing:.1em}}.metric b{{font-size:2rem}}.ratio{{font-size:1.45rem;font-weight:850;color:var(--blue);margin-top:10px}}.viz{{width:100%;height:auto;display:block;margin-top:14px}}.pillars{{display:grid;grid-template-columns:repeat(3,1fr);gap:13px}}.pillars article{{border:1px solid var(--line);border-top:5px solid var(--blue);border-radius:13px;padding:17px;background:#fff}}.pillars article:nth-child(2){{border-top-color:var(--gold)}}.pillars article:nth-child(3){{border-top-color:var(--teal)}}small{{display:block;letter-spacing:.13em;font-weight:850;color:var(--blue)}}strong{{display:block;font-size:1.2rem;margin:6px 0}}em{{font-size:.86rem;color:var(--muted);font-style:normal}}.gap{{padding:11px 13px;background:#fff4da;border-left:4px solid var(--gold);color:#61491d}}.equation{{text-align:center;font-size:clamp(1.4rem,3vw,2.2rem);font-weight:900;color:var(--blue)}}.function{{background:var(--navy);color:#fff}}.function p{{color:#d9e3ea}}.function-name{{font-size:1.8rem;font-weight:850}}footer{{margin-top:24px;padding-top:14px;border-top:1px solid var(--line);font-size:.8rem;color:var(--muted)}}@media(max-width:760px){{main{{padding:20px 14px}}.summary,.pillars{{grid-template-columns:1fr}}}}
</style></head><body><main><div class="top"><div class="tag">Version C · Executive evidence dashboard</div><div class="hold">PUBLICATION STATUS: HOLD / REVIEW REQUIRED</div></div>
<h1>Where does disparity emerge in the AI-assisted employment system—and who should own investigating it?</h1>
<p class="thesis">The available evidence measures observed hiring composition and candidate-facing recruiting signals. It does not locate the source of disparity or establish that Greenhouse caused an outcome. Internal stage and workflow instrumentation is needed to test where differences emerge.</p>
<section class="panel summary"><div><h2>Observed outcome environment</h2><p>{sum(counts.values()):,} observed people · UNKNOWN retained separately</p><div class="metrics">{cards}</div><div class="ratio">{data['male_female_ratio']:.2f}:1 observed MALE/FEMALE ratio</div><p>Known-sex composition: {pct['male']:.1f}% MALE / {pct['female']:.1f}% FEMALE</p></div><div><h2>Known-sex composition</h2><svg class="viz" viewBox="0 0 560 125" role="img" aria-label="Known sex composition: {pct['male']:.1f}% Male and {pct['female']:.1f}% Female"><rect x="8" y="35" width="544" height="34" rx="17" fill="#e5e9eb"/><path d="M25 35 H{25+510*pct['male']/100} V69 H25 Q8 69 8 52 Q8 35 25 35" fill="#315f82"/><path d="M{25+510*pct['male']/100} 35 H535 Q552 35 552 52 Q552 69 535 69 H{25+510*pct['male']/100} Z" fill="#cf9a4a"/><text x="10" y="105" fill="#315f82" font-size="16" font-weight="700">MALE {pct['male']:.1f}%</text><text x="370" y="105" fill="#805b22" font-size="16" font-weight="700">FEMALE {pct['female']:.1f}%</text></svg></div></section>
<section class="panel"><h2>Evidence layers</h2><div class="pillars">{''.join(findings)}</div></section>
<section class="panel"><div class="equation">MODEL FAIRNESS ≠ WORKFLOW FAIRNESS ≠ OUTCOME FAIRNESS</div><p>Observed representation is a reason to investigate. It is not proof of adverse impact, model bias, candidate-level discrimination, or causality.</p></section>
<section class="panel function"><div class="tag" style="color:#a9d9d2">PROPOSED EXECUTIVE CAPABILITY</div><div class="function-name">Human-AI Employment Intelligence &amp; Governance</div><p>Coordinate recruiting technology, human decision-making, employment practices, and advancement evidence to identify mechanisms and evaluate measurable interventions.</p></section>
{gap_html}<footer>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from frozen Version C aggregates. Inline SVG/CSS only; no external JavaScript or network assets. Controlled executive review copy. GitHub destination metadata: {GITHUB}</footer></main></body></html>'''
    OUT.mkdir(parents=True,exist_ok=True); TARGET.write_text(document,encoding="utf-8")
    print("STEP 10 — FINAL EXECUTIVE DASHBOARD BUILT")
    print(f"STATUS: {'PASS_WITH_GAPS' if gaps else 'PASS'}")
    print(f"OUTCOMES: {counts['MALE']} / {counts['FEMALE']} / {counts['UNKNOWN']} / {sum(counts.values())}")
    print("PREDICTION: NOT ESTIMABLE FROM PUBLIC DATA")
    print(f"MISSING PRIOR AUDITS: {len(gaps)}")
    print(f"DASHBOARD: {TARGET}")
    return 0

if __name__=="__main__": raise SystemExit(main())
