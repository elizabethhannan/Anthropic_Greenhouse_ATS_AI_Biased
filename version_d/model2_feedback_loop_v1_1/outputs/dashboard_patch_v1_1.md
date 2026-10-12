# Replit Agent prompt: Model 2 v1.1 dashboard patch (NOT YET APPLIED)

**Status:** written 2026-10-11; Elizabeth paused Replit updates. Paste this into the Replit Agent only when she says to.

---

Load `model2_v1_1_results.json` (from `version_d/model2_feedback_loop_v1_1/outputs/`). In **section 07 (Simulation)**, add two panels after E3. Both use the purple family only (#5b3f8c, #8a6fbf, #c9b8e6, neutral gray), carry a **SIMULATION** tag, and repeat the label "SIMULATION — synthetic applicants; not Anthropic data". Never call anything a forecast.

**E4 Reliance.** Small multiples, one per scenario (S1 even-handed interviews, S2 interview penalty continues) and calibration (C1, C2). x-axis: w (interviewer reliance on the AI score: 0, 0.25, 0.5, 0.75). y-axis: overall impact ratio at cycle 8 (`extensions[id="X1"].results[*].overall_ir.median[7]`, with p05/p95 as a band). Dashed line at 0.80. Caption: the first two sentences of `findings`.

**E5 Minimum instrumentation.** A readable grid from `power.rows`: rows = stage × true ratio, columns = applicants per role family per period (250, 500, 1,000, 2,000, 5,000, 10,000); cell = power, shaded light to dark purple; highlight cells ≥ 0.80. Above the grid, one line per stage and pool share: "Applicants per role family needed to detect a gap of 0.62 with 80% power: {min_applicants_80pct}". Caption: the third sentence of `findings`.

Do not change any other section. Keep the existing "Algorithmic causation: Not established" and "Historical feedback loops: Exploratory hypothesis" labels as they are.
