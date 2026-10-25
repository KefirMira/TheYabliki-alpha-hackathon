"""Internal safe diagnostics, no free-text exception fields."""
from typing import Literal
from pydantic import BaseModel, ConfigDict


class PreparationDiagnostic(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    version: Literal['safe-preparation-diagnostic-v1'] = 'safe-preparation-diagnostic-v1'
    stage: Literal['load_snapshot','company_context','rag_search','prepare_input',
                   'transfer_check','local_stub','self_check','UNKNOWN']
    family: Literal['DATABASE','SCHEMA','VALUE','TYPE','RUNTIME','CANCEL_OR_TIMEOUT','UNKNOWN']
    historical_root_cause: Literal['UNKNOWN'] = 'UNKNOWN'
    retry_allowed: Literal[False] = False
