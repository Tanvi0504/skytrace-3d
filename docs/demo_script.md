# 2–3 minute judge demo

1. Introduce the problem: a single drone flight must yield an inspectable 3D scene despite limited viewpoints and imperfect sensing.
2. Run `python -m skytrace.system_check`; show either `READY` or the exact readiness blocker.
3. In the UI, create a new analysis, upload an authorised MP4, and click **Process**. Explain that the displayed states come from real pipeline stages, not simulated percentages.
4. Show the input report and selected-frame count, then the reconstruction progress/result.
5. Open the 3D scene, rotate it, and identify visible terrain/structures/roads only where present in the actual input.
6. Select an object marker. Show observation count, 3D-position status, and evidence—not a fabricated motion or coordinate claim.
7. Enable the evidence layer and make a distance measurement. Call out the reliability warning/level.
8. Show `skytrace_report.html` and the result manifest. Point out limitations and stage durations.
9. If live reconstruction fails, say **“PRE-PROCESSED DEMO RESULT”**, open `/viewer/processed-demo`, and state that it is a backup, not the upload's output.
10. Close with the distinction: SkyTrace packages a single-pass reconstruction with traceable evidence and explicit failure boundaries rather than promising complete or survey-grade geometry.

Do not demo unverified accuracy, an unlicensed clip, an unavailable model, or a fabricated real-time claim.
