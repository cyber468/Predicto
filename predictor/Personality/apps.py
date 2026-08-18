from pathlib import Path

from django.apps import AppConfig
import pickle

# repo_root/predictor/Personality/apps.py -> repo_root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = REPO_ROOT / "ml" / "models" / "final_model.pkl"


class PersonalityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Personality'
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
