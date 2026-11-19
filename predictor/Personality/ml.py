"""Loads the trained KMeans model once and turns answers into trait scores.

Two kinds of numbers appear here and must not be mixed up:
  * raw answers: how much the person agreed with each statement, 1 (disagree) to 5 (agree). The pickled model
    was trained on this raw scale, so it is the only thing ever passed to model.predict().
  * keyed scores: raw answers with the negatively keyed items flipped (6 - x), as the IPIP scoring key says.
    Trait scores are averaged from these.
"""
import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np

from .questions import QUESTIONS

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = REPO_ROOT / "ml" / "models" / "final_model.pkl"
ITEMS_PER_TRAIT = 10
N_ITEMS = 50
REVERSED = np.array([rev for _, rev in QUESTIONS])


@lru_cache(maxsize=1)
def get_model():
    # The file ships with the repo and is trusted. Never point this at user uploads.
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def keyed(raw):
    """Apply the IPIP scoring key to raw 1-5 answers."""
    raw = np.asarray(raw, dtype=float)
    return np.where(REVERSED, 6 - raw, raw)


def trait_scores(raw):
    """Mean keyed score of each trait's 10 items, rescaled from 1-5 to 0-100."""
    arr = keyed(raw).reshape(5, ITEMS_PER_TRAIT)
    return [round(float(x), 2) for x in arr.mean(axis=1) / 5 * 100]


def predict(raw):
    """Return (cluster id, trait scores of that cluster's centroid). `raw` must be raw 1-5 answers."""
    model = get_model()
    cluster = int(model.predict([list(raw)])[0])
    return cluster, trait_scores(model.cluster_centers_[cluster])
