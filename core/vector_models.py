import logging
from typing import TYPE_CHECKING
from fastembed import TextEmbedding, SparseTextEmbedding

logger = logging.getLogger(__name__)

# Блок выполняется ТОЛЬКО статическими анализаторами (Pylance, MyPy).
# В рантайме (при работе программы) этот код полностью игнорируется,
# поэтому тяжелые библиотеки здесь импортировать абсолютно БЕЗОПАСНО.
if TYPE_CHECKING:
    from fastembed import TextEmbedding, SparseTextEmbedding

class VectorModelsState:
    """Приватный контейнер для хранения тяжелых ИИ-моделей в оперативной памяти."""
    def __init__(self) -> None:
        self.dense: TextEmbedding | None = None
        self.sparse: SparseTextEmbedding | None = None

# Единственный экземпляр состояния на весь процесс приложения (синглтон)
_state = VectorModelsState()

def init_vector_models() -> None:
    """Вызывается строго 1 раз в lifespan при старте FastAPI."""
    logger.info("Загрузка тяжелых ИИ-моделей в память (Dense + Sparse)...")
    
    # Настройки сессии ONNX (тяжелый пакет, лучше импортировать когда необходимо)
    import onnxruntime as ort

    # 1. Создаем настройки для ONNX Runtime
    session_options = ort.SessionOptions()

    # Ограничиваем количество потоков (Внутренние потоки C++)
    session_options.intra_op_num_threads = 2
    session_options.inter_op_num_threads = 2

    # Отключаем глобальный пул потоков, чтобы сессия использовала только свои личные
    session_options.use_per_session_threads = True
    
    # Инициализируем локальные эмбеддинги
    # Кэш Hugging Face (~/.cache/huggingface)
    _state.dense = TextEmbedding(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        session_options=session_options
    )
    
    # Кэш FastEmbed ($TMPDIR/fastembed_cache)
    # Для удобного монтирования в docker: cp -r "$TMPDIR/fastembed_cache" ~/.cache/
    _state.sparse = SparseTextEmbedding(
        model_name="prithivida/Splade_PP_en_v1",
        session_options=session_options
    )
    
    logger.info("ИИ-модели успешно загружены в контейнер состояния.")

def get_dense_model() -> TextEmbedding:
    if _state.dense is None:
        raise RuntimeError("Dense модель не была инициализирована! Вызовите init_ai_models() в lifespan.")
    return _state.dense

def get_sparse_model() -> SparseTextEmbedding:
    if _state.sparse is None:
        raise RuntimeError("Sparse модель не была инициализирована! Вызовите init_ai_models() в lifespan.")
    return _state.sparse
