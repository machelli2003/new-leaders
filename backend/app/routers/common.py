from __future__ import annotations

from typing import Optional

from pydantic import create_model


def partial(model):
    """Clone a Pydantic model with every field optional (for PATCH bodies)."""
    fields = {n: (Optional[f.annotation], None) for n, f in model.model_fields.items()}
    return create_model(f"{model.__name__}Patch", **fields)
