"""Les tests s'exécutent sans clé API : tout appel réel à un modèle est interdit."""

import os

os.environ.setdefault('MISTRAL_API_KEY', 'cle-de-test')

from pydantic_ai import models  # noqa: E402

models.ALLOW_MODEL_REQUESTS = False
