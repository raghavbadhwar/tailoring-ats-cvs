# Formatting optimization contract

Formatting optimization is a two-step process:

1. Extract text from the source document with a reviewed adapter and preserve the original.
2. Run `ats-agent format resume.txt --json`, then apply approved formatting changes in a duplicate document.

The audit checks extractable text, dense lines, tabular spacing, decorative bullets, and detectable section headings. Recommended output uses one column, ordinary headings, consistent dates, plain links, standard bullets, readable body text, and no tables, text boxes, headers/footers, graphics, photos, or skill bars.

The tool reports parser risk only. It does not predict a specific employer's ranking or acceptance decision.
