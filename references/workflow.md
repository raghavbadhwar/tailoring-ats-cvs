# Workflow contract

`PROPOSE` is read-only. It reports hard eligibility gates, parser risks, requirement-to-evidence mappings, exact and semantic keywords, unsupported claims, and numbered proposed changes.

The report is assembled by deterministic stages: ATS parser, JD intelligence, keyword strategy, language optimization, recruiter simulation, hiring-manager review, evidence/achievement audit, company-language alignment, and interview defense. Each stage returns structured data under `report.agents` so a future model adapter can improve recommendations without changing the safety contract.

`APPLY` accepts only an explicit allow-list of change IDs. It preserves the source, records an applied-change log, and reruns the parser-risk checks. A job description is vocabulary, never evidence.
