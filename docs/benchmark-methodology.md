# Benchmark v3 Methodology

Benchmark v3 is a frozen, offline evaluation suite for the evidence-grounded CV-tailoring engine. It measures deterministic behaviour; it does not estimate interview probability, employer acceptance, or compatibility with every applicant-tracking system.

## Suites

| Suite | Cases | Purpose |
|---|---:|---|
| `smoke` | 8 | Installed-wheel and command-line smoke testing |
| `public` | 180 | Requirement extraction, evidence matching, hard gates, rewrite safety, variants, section placement, and latency |
| `adversarial` | 60 | Twenty attack and failure classes, with three independently worded cases per class |
| `documents` | 30 | DOCX, text-PDF, RTF, and HTML parsing, including malformed and hidden-content cases |
| `human` | 50 | Blinded human-review queue; ratings remain null until independent reviewers complete them |

The public suite contains 36 cases in each of five role families: AI and automation, finance and analytics, consulting and operations, product and programme work, and software and data.

## Labelling

Labels are stored in JSONL and are not generated from engine predictions at benchmark runtime. Every case identifies its label source as `curated-static`. Expected requirements include source spans. Compact matrix records expand deterministically into frozen cases without consulting the engine under test.

The suites are synthetic and privacy-safe. They are intended for regression and safety evaluation, not as evidence of real-world hiring outcomes. Human preference is reported only after blinded ratings are supplied.

## Diversity guard

`python scripts/validate_benchmark_diversity.py` fails when it finds duplicate normalized resume/job-description pairs, number-only mutations, overrepresented templates or role families, missing labels or spans, or engine-generated labels.

The legacy repeated five-template benchmark is retained only under `benchmarks/legacy-v0.9/` for historical comparison and is not used for release gates.

## Metrics

Reports include numerators, denominators, values, 95% Wilson intervals where applicable, the dataset SHA-256, code SHA, execution timestamp, Python version, and platform. Parser-risk delta and human preference remain `not_measured` unless a dedicated measurement is actually supplied.

## Release use

```bash
ats-agent benchmark --suite public --report benchmarks/v3/reports/public.json
ats-agent benchmark --suite adversarial --report benchmarks/v3/reports/adversarial.json
ats-agent benchmark --suite documents --report benchmarks/v3/reports/documents.json
python scripts/validate_benchmark_diversity.py
python scripts/check_benchmark.py
```

The private holdout is intentionally not committed. The release workflow accepts a pinned holdout JSONL supplied through the protected `release` environment, records its SHA-256, and fails closed when the holdout is absent for a publication run.
