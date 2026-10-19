# Release process

The project uses a fail-closed beta release process. A green pull-request check is necessary but not sufficient for publication.

## Required checks before merge

1. `CI / quality` passes with branch coverage of at least 90%.
2. Linux and Windows compatibility jobs pass on Python 3.10, 3.11, 3.12, and 3.13.
3. Benchmark v3 public, adversarial, and document gates pass.
4. `Security / python-security` and CodeQL pass.
5. Dependency review reports no new high-severity dependency issue.
6. The installed wheel is smoke-tested outside the repository checkout.

## Protected private holdout

The 60-case private holdout must not be committed to the public repository. Configure a GitHub environment named `release` with a secret named `PRIVATE_HOLDOUT_B64` containing the Base64-encoded Benchmark v3 public-schema JSONL holdout.

The release workflow decodes the secret into an ephemeral runner file, runs `scripts/release_check.py --private-holdout ...`, records the holdout SHA-256 and aggregate metrics, and never uploads the private cases themselves.

The private holdout is a release blocker. If the secret is absent, malformed, contains fewer than 60 cases, or fails the release thresholds, the release job fails.

## Beta publication

After PR checks pass on the exact head:

1. Merge the trustworthy-v1 PR into `main`.
2. Confirm the exact merged SHA passes the required workflows.
3. Create the annotated tag `v1.0.0-beta.3` on that exact SHA.
4. The tag-triggered `Release` workflow reruns release gates, the private holdout, security checks, package build, clean-wheel install, SBOM generation, and checksums.
5. Only after those steps pass does the workflow create the GitHub prerelease.

Release assets include the wheel, source distribution, Codex skill ZIP, Claude Code plugin ZIP, CycloneDX SBOM, SHA-256 checksums, release-check metadata, and public Benchmark v3 reports.

## Stable v1.0

Do not promote the beta to stable `v1.0.0` until the 25-pair anonymized real-document pilot and the blinded human rewrite evaluation are complete. Stable-release claims must remain limited to measured properties; the project does not claim a universal ATS score, interview probability, or employer-acceptance probability.
