# Stable-v1 real-document pilot protocol

This pilot is a product-validation gate, not an automated benchmark and not evidence of employer acceptance.

## Sample

Use 25 anonymized CV–job-description pairs covering at least five role families. Remove names, email addresses, phone numbers, addresses, account identifiers, and any evidence that is not needed to judge the rewrite.

For each pair, preserve an immutable copy of the original CV, job description, evidence inputs, proposal digest, approval manifest, output document, and apply receipt.

## Procedure

1. Run the exact beta wheel that passed the protected release workflow.
2. Generate the proposal and full review bundle.
3. A human reviewer selects or rejects proposed changes; the system must not auto-approve.
4. Apply only the approved manifest.
5. Reopen the resulting DOCX in a normal office suite and inspect every page visually.
6. Record any factual correction, wording correction, formatting repair, blocked operation, provider fallback, and total review time.

## Required fields per pair

- anonymized case ID
- role family
- input and output SHA-256 values
- proposal digest
- number of proposed changes
- number approved
- number applied successfully
- number requiring factual correction
- number requiring wording correction
- visual repair required: yes/no
- blocked-operation reasons
- provider fallback count
- review time in minutes
- reviewer notes

## Stable-release gates

Stable `v1.0.0` remains blocked unless:

- at least 25 pairs are completed;
- at least 95% of DOCX outputs pass human visual review without manual repair;
- approved-change correction rate is below 10%;
- no P0/P1 factual-safety defect remains open;
- the separate blinded human rewrite evaluation is complete.

Do not use interview invitations, application progression, or hiring outcomes as a release gate without a sufficiently powered longitudinal study.
