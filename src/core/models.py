from dataclasses import dataclass
from typing import Optional


@dataclass
class DiagnosticoIA:
    diagnostico: str
    severidade: str
    comando_remediacao: str


@dataclass
class IncidenteRede:
    incidente_id: str
    equipamento: str
    severidade: str
    diagnostico: str
    comando_remediacao: str
    s3_key: Optional[str] = None
    status: str = "PENDENTE"