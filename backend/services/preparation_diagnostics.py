"""Allowlisted categories only: never stringify exceptions, causes, SQL or locals."""
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from schemas.preparation_diagnostics import PreparationDiagnostic

STAGES = {'load_snapshot','company_context','rag_search','prepare_input',
          'transfer_check','local_stub','self_check'}


def safe_diagnostic(stage, error):
    # isinstance does not access repr, str, args, __cause__, SQLSTATE or a custom class name.
    family = next((label for kind,label in ((SQLAlchemyError,'DATABASE'),
        (ValidationError,'SCHEMA'),(TimeoutError,'CANCEL_OR_TIMEOUT'),(TypeError,'TYPE'),
        (ValueError,'VALUE'),(RuntimeError,'RUNTIME')) if isinstance(error,kind)), 'UNKNOWN')
    return PreparationDiagnostic(stage=stage if stage in STAGES else 'UNKNOWN',family=family)
