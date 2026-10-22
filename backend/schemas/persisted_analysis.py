"""Internal persistence contract; does not replace the legacy HTTP response."""

from pydantic import BaseModel, Field, model_validator

from schemas.analysis import CompanyAnalysisResponse


class RetrievedEvidence(BaseModel):
    id: int = Field(gt=0)
    document: str = Field(min_length=1)
    page: int = Field(gt=0)
    chunk_id: int = Field(gt=0)
    date: str | None = None
    score: float = Field(ge=0, allow_inf_nan=False)
    text: str = Field(min_length=1)


class PersistableAnalysis(BaseModel):
    analysis: CompanyAnalysisResponse
    evidence: list[RetrievedEvidence] = Field(min_length=1)
    model_name: str | None = None
    prompt_version: str = "company-json-v1"

    @model_validator(mode="after")
    def check_sources(self):
        sources = {source.id: source for source in self.analysis.sources}
        fragments = {fragment.id: fragment for fragment in self.evidence}
        if len(sources) != len(self.analysis.sources) or len(fragments) != len(self.evidence):
            raise ValueError("Duplicate source identifiers")
        if sources.keys() != fragments.keys():
            raise ValueError("Every source must have a retrieved fragment")
        for key, source in sources.items():
            fragment = fragments[key]
            if (source.document, source.page, source.score) != (fragment.document, fragment.page, fragment.score):
                raise ValueError("Source metadata does not match retrieved fragment")
        return self
