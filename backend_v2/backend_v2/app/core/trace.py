from datetime import datetime, timezone
from uuid import uuid4


def gerar_trace_id(prefixo: str, aluno_id: int | str | None = None) -> str:
    partes = [prefixo]
    if aluno_id is not None:
        partes.append(str(aluno_id))
    partes.append(datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    partes.append(uuid4().hex[:8])
    return "-".join(partes)
