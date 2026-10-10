from pydantic import BaseModel, Field


class Product(BaseModel):
    count: int = Field(default=0, ge=1, validate_default=True)
