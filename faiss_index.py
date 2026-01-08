# src/faiss_index.py
import numpy as np
from typing import List, Dict, Tuple
import os

# Attempt to import sentence-transformers; otherwise fallback to sklearn Tfidf
try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except Exception:
    _HAS_ST = False
    from sklearn.feature_extraction.text import TfidfVectorizer

import faiss

MODEL_NAME = "all-MiniLM-L6-v2"

class FaissIndexWrapper:
    def __init__(self, dim: int):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)  # inner product (use normalized vectors for cosine)
        self.id_to_meta = []  # list of metadata dicts

    def add(self, vectors: np.ndarray, metas: List[Dict]):
        # vectors: (n, dim)
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)
        self.index.add(vectors)
        self.id_to_meta.extend(metas)

    def query(self, vector: np.ndarray, top_k: int = 10) -> List[Tuple[int, float, Dict]]:
        if vector.dtype != np.float32:
            vector = vector.astype(np.float32)
        if vector.ndim == 1:
            vector = vector.reshape(1, -1)
        D, I = self.index.search(vector, top_k)
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            results.append((idx, float(score), self.id_to_meta[idx]))
        return results

def compute_embeddings(texts: List[str]):
    """
    Compute dense embeddings. Try sentence-transformers fallback to TF-IDF dense vectors.
    Returns numpy array (n, dim) and a string indicating provider.
    """
    if _HAS_ST:
        model = SentenceTransformer(MODEL_NAME)
        embs = model.encode(texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
        # normalize for inner-product cosine sim when using IndexFlatIP
        return embs.astype("float32"), f"sentence-transformers:{MODEL_NAME}"
    else:
        # TF-IDF fallback
        vect = TfidfVectorizer(max_features=4096)
        X = vect.fit_transform(texts)
        X = X.toarray().astype("float32")
        # normalize rows
        norms = np.linalg.norm(X, axis=1, keepdims=True) + 1e-10
        X = X / norms
        return X, "tfidf-fallback"

def build_faiss_index(docs: List[Dict], text_key: str = "content") -> Tuple[FaissIndexWrapper, str]:
    texts = [d.get(text_key, "") for d in docs]
    embs, provider = compute_embeddings(texts)
    dim = embs.shape[1]
    idx = FaissIndexWrapper(dim)
    metas = [{"path": d.get("path"), "lang": d.get("lang")} for d in docs]
    idx.add(embs, metas)
    return idx, provider
