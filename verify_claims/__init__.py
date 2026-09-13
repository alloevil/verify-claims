"""verify-claims — run the receipts behind a claims.json file."""

from .cli import main
from .checks import CheckResult, evaluate, exit_code_for, summarise
from .runner import run_claim, run_commands
from .schema import DATE_FIELDS, validate_document

__version__ = "0.1.2"
__all__ = [
    "CheckResult",
    "DATE_FIELDS",
    "__version__",
    "evaluate",
    "exit_code_for",
    "main",
    "run_claim",
    "run_commands",
    "summarise",
    "validate_document",
]
