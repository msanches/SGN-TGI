# app/utils/instruments.py
from app.models import Instrument

# mapeia apelidos -> possíveis nomes no Enum
_CANDIDATES = {
    "ri":  ("RI", "RELATORIO_I", "RelatorioI"),
    "rii": ("RII", "RELATORIO_II", "RelatorioII"),
    "paper": ("PAPER", "Paper", "ARTIGO"),
}

def resolve_instrument(key: str) -> Instrument:
    """Aceita 'ri', 'rii', 'paper' e resolve para o membro correto do Enum Instrument,
    seja pelo .name (RI/RELATORIO_I/...) ou pelo .value ('ri', 'relatorio_i', ...)."""
    k = (key or "").strip().lower()
    if not k:
        raise ValueError("instrument key vazio")

    # 1) tenta por name (vários candidatos)
    for name in _CANDIDATES.get(k, ()):
        if hasattr(Instrument, name):
            return getattr(Instrument, name)

    # 2) tenta por value (string armazenada no banco)
    for m in Instrument:
        val = str(m.value).lower()
        if val in {k, f"relatorio_{k}"}:
            return m

    raise AttributeError(f"Instrument '{key}' não encontrado no Enum Instrument. "
                         f"Disponíveis: names={[m.name for m in Instrument]}, values={[m.value for m in Instrument]}")
