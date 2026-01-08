# src/preprocess.py
from utils.file_utils import read_file, detect_language
from utils.winnowing import tokens_from_code, winnow_hashes
from utils.ast_utils import canonical_ast_node_types
from typing import Dict, Any
from faiss_index import compute_embeddings
import numpy as np

def preprocess_file(path: str, k: int = 5, w: int = 4) -> Dict[str, Any]:
    content = read_file(path)
    lang = detect_language(path)
    tokens = tokens_from_code(content)
    fingerprint = winnow_hashes(tokens, k=k, w=w)
    ast_types = None
    if lang == "python":
        ast_types = canonical_ast_node_types(content)
    # compute per-file embedding (single-vector)
    # compute_embeddings expects a list, so call once externally for all files to be efficient.
    # For convenience here we compute a placeholder; agent will compute real embeddings in batch.
    embedding = None
    if content:
        # placeholder zero vector — replaced by faiss build step in agent
        embedding = np.zeros((1,), dtype="float32")
    return {
        "path": path,
        "lang": lang,
        "content": content,
        "tokens": tokens,
        "fingerprint": fingerprint,
        "ast_types": ast_types,
        "embedding": embedding
    }
