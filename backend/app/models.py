from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


class Customer(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(default="", max_length=40)
    contactPreference: str = Field(default="Correo electrónico", max_length=60)


class OrderLine(BaseModel):
    id: str = Field(min_length=2, max_length=60)
    name: str = Field(default="", max_length=120)
    price: int = Field(default=0, ge=0)


class DraftOrder(BaseModel):
    id: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default="borrador", max_length=40)
    customer: Customer
    projectType: str = Field(min_length=2, max_length=120)
    area: str = Field(default="", max_length=40)
    requirements: str = Field(default="", max_length=2000)
    budget: str = Field(default="", max_length=120)
    items: list[OrderLine] = Field(min_length=1)
    total: int = Field(default=0, ge=0)

    @field_validator("items")
    @classmethod
    def unique_items(cls, items: list[OrderLine]) -> list[OrderLine]:
        ids = [item.id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("No se permiten servicios duplicados.")
        return items


class CheckoutRequest(BaseModel):
    order: DraftOrder


class OrderResponse(BaseModel):
    id: str
    status: str
    total: int
    createdAt: datetime
    checkoutUrl: str | None = None
