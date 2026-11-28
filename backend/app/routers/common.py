from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException
from pydantic import create_model


def partial(model):
    """Clone a Pydantic model with every field optional (for PATCH bodies)."""
    fields = {n: (Optional[f.annotation], None) for n, f in model.model_fields.items()}
    return create_model(f"{model.__name__}Patch", **fields)


def literal_search_regex(value: str) -> dict[str, str]:
    if len(value) > 100:
        raise HTTPException(422, "Search query must be at most 100 characters")
    return {"$regex": re.escape(value), "$options": "i"}
