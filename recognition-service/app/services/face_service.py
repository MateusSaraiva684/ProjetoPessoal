import logging
from typing import Optional, Tuple
from threading import Lock

import cv2
import numpy as np
from insightface.app import FaceAnalysis

logger = logging.getLogger(__name__)

# Singleton + thread-safe
_face_app: Optional[FaceAnalysis] = None
_lock = Lock()


def get_face_app(use_gpu: bool = True) -> FaceAnalysis:
    """
    Inicializa e retorna o modelo InsightFace com controle de concorrência.
    """
    global _face_app

    if _face_app is None:
        with _lock:
            if _face_app is None:
                logger.info("Inicializando modelo InsightFace...")

                try:
                    providers = (
                        ["CUDAExecutionProvider", "CPUExecutionProvider"]
                        if use_gpu
                        else ["CPUExecutionProvider"]
                    )

                    _face_app = FaceAnalysis(
                        name="buffalo_l",
                        providers=providers
                    )

                    ctx_id = 0 if use_gpu else -1
                    _face_app.prepare(ctx_id=ctx_id)

                    logger.info(f"Modelo carregado (GPU={use_gpu})")

                except Exception as e:
                    logger.error(f"Erro ao carregar modelo: {e}", exc_info=True)
                    raise RuntimeError("Falha ao inicializar modelo de IA")

    return _face_app


def is_model_loaded() -> bool:
    return _face_app is not None


def _is_blurry(img: np.ndarray, threshold: float = 100.0) -> bool:
    """
    Detecta se a imagem está borrada usando Laplacian.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

    logger.debug(f"Blur score: {blur_score:.2f}")
    return blur_score < threshold


def _select_best_face(faces) -> Optional[object]:
    """
    Seleciona a melhor face baseada em score + área.
    """
    if not faces:
        return None

    return max(
        faces,
        key=lambda f: (
            f.det_score,
            (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
        )
    )


def get_embedding(
    image_bytes: bytes,
    use_gpu: bool = True,
    enforce_quality: bool = True
) -> Optional[np.ndarray]:
    """
    Extrai embedding facial normalizado.

    Args:
        image_bytes: imagem em bytes
        use_gpu: usar GPU ou não
        enforce_quality: filtrar imagens ruins

    Returns:
        np.ndarray normalizado ou None
    """
    try:
        if not image_bytes:
            raise ValueError("image_bytes está vazio")

        # Decode
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Imagem inválida ou formato não suportado")

        logger.debug(f"Imagem recebida: {img.shape}")

        # 🔥 BGR -> RGB (CRÍTICO)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 🔥 Filtro de qualidade
        if enforce_quality and _is_blurry(img):
            logger.warning("Imagem descartada: borrada")
            return None

        # Modelo
        app = get_face_app(use_gpu=use_gpu)

        # Detecção
        faces = app.get(img)

        if not faces:
            logger.info("Nenhum rosto detectado")
            return None

        # 🔥 Escolha inteligente
        face = _select_best_face(faces)

        if face is None:
            return None

        # Embedding
        embedding = face.embedding

        if embedding is None:
            logger.warning("Falha ao extrair embedding")
            return None

        # 🔥 NORMALIZAÇÃO (OBRIGATÓRIO)
        norm = np.linalg.norm(embedding)
        if norm == 0:
            logger.warning("Embedding com norma zero")
            return None

        embedding = embedding / norm

        logger.debug(f"Embedding extraído (dim={embedding.shape})")

        return embedding.astype(np.float32)

    except ValueError as e:
        logger.error(f"Erro de validação: {e}")
        raise

    except Exception as e:
        logger.error("Erro inesperado no processamento", exc_info=True)
        raise RuntimeError(f"Erro ao processar imagem: {str(e)}")

def save_embedding(db, aluno_id: int, embedding: np.ndarray):
    """
    Salva embedding na tabela embeddings
    """
    db.execute(
        "INSERT INTO embeddings (aluno_id, embedding) VALUES (%s, %s)",
        (aluno_id, embedding.tolist())
    )
    db.commit()        
