from decimal import Decimal

import pytest

from ats_agent.claim_validation import ClaimValidationError, verify_variant_claims
from ats_agent.models import AtomicClaim, SourceSpan


def test_unrelated_number_cannot_authorize_new_metric() -> None:
    claim = AtomicClaim(claim_id="EC1", candidate_id="candidate-a", artifact_id="portfolio", source_span=SourceSpan(part="body", line_number=4), source_text="Processed 50 invoices.", action="processed", metric_value=Decimal("50"), metric_unit="invoices", metric_scope="processed", ownership="direct", verification="candidate_supplied", confidence=0.95)
    with pytest.raises(ClaimValidationError, match="metric binding"):
        verify_variant_claims("Built a finance workflow.", "Built a finance workflow that increased revenue by 50%.", [claim])
