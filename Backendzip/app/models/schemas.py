from pydantic import BaseModel
from typing import Optional


class Claim(BaseModel):
    id: str
    document_id: str

    subject: str
    predicate: str

    value: Optional[float] = None
    value_type: Optional[str] = None
    unit: Optional[str] = None

    period_start: Optional[str] = None
    period_end: Optional[str] = None
    period_type: Optional[str] = None

    scope: Optional[str] = None
    basis: Optional[str] = None
    definition: Optional[str] = None

    claim_type: Optional[str] = None

    source_page: int
    source_text: str

    verified: bool

    confidence: Optional[float] = None


class Relationship(BaseModel):
    id: str

    source_claim_id: str
    target_claim_id: str

    relationship_type: str
    reason_code: str
    explanation: str

    confidence: Optional[float] = None

    decided_by: str


class ExtractedClaimRaw(BaseModel):
    """
    What we ask the LLM to return for a claim extracted from
    one of the evidence blocks in a batch.
    """

    block_id: str

    subject: str
    predicate: str

    value: Optional[float] = None
    value_type: Optional[str] = None
    unit: Optional[str] = None

    period_start: Optional[str] = None
    period_end: Optional[str] = None
    period_type: Optional[str] = None

    scope: Optional[str] = None
    basis: Optional[str] = None
    definition: Optional[str] = None

    claim_type: Optional[str] = None

    evidence_quote: str

    confidence: float = 0.5