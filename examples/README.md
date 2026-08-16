# Reproducible example

The files in this directory are synthetic and contain no real candidate contact data.

From the repository root:

```bash
python -m pip install -e ".[dev,documents]"

ats-agent prepare \
  examples/sample_resume.txt \
  examples/sample_job.md \
  --candidate-id sample-candidate \
  --evidence examples/sample_evidence.md \
  --review-dir run
```

Open `run/review.html`, inspect the evidence for every proposed change, select rewrite variants, and download `approval-manifest.json`.

The downloaded manifest references `proposal.json`. Place it in the same `run/` directory or adjust the `proposal` path. Add an explicit output path, for example:

```json
{
  "proposal": "proposal.json",
  "approved_change_ids": ["C1"],
  "selected_variants": {"C1": "balanced"},
  "output": "sample_resume.tailored.txt",
  "output_mode": "preserve"
}
```

Then apply and validate:

```bash
ats-agent apply run/approval-manifest.json
ats-agent validate run/sample_resume.tailored.txt
```

The source resume is never overwritten. Unsupported requirements such as Kubernetes remain visible gaps and are not inserted into the CV.

For an automated end-to-end check, run:

```bash
python scripts/smoke_example.py
```
