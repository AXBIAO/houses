"""出租与收租的请求体。金额一律 Decimal，前端可传数字或字符串。"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PHONE_RE = re.compile(r"^1\d{10}$")
MONEY = dict(max_digits=12, decimal_places=2)
PRICE = dict(max_digits=10, decimal_places=4)


class RenterIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    phone: str
    idCardTail: str | None = Field(None, description="证件号末 4 位，仅用于核对")
    note: str = Field("", max_length=200)

    @field_validator("name", "note")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_RE.fullmatch(value):
            raise ValueError("手机号格式不正确")
        return value

    @field_validator("idCardTail")
    @classmethod
    def _tail(cls, value: str | None) -> str | None:
        value = (value or "").strip().upper() or None
        if value is not None and not re.fullmatch(r"[0-9X]{4}", value):
            raise ValueError("证件号只需填写末 4 位")
        return value

    @model_validator(mode="after")
    def _name(self) -> "RenterIn":
        if not self.name:
            raise ValueError("请填写租客姓名")
        return self

    def to_db(self) -> dict[str, Any]:
        return {"name": self.name, "phone": self.phone, "id_card_tail": self.idCardTail, "note": self.note}


class FeeItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    kind: Literal["fixed", "one_time", "metered"]
    defaultPrice: Decimal = Field(ge=0, **PRICE)
    unit: str = Field("", max_length=8)
    active: bool = True

    @field_validator("name", "unit")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip()

    def to_db(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "default_price": self.defaultPrice, "unit": self.unit, "active": self.active}


class FeeChoiceIn(BaseModel):
    feeItemId: int = Field(gt=0)
    price: Decimal | None = Field(None, ge=0, **PRICE)


class LeaseSignIn(BaseModel):
    listingId: int = Field(gt=0)
    renterId: int | None = Field(None, gt=0)
    newRenter: RenterIn | None = None
    startDate: date
    endDate: date
    monthlyRent: Decimal = Field(ge=0, **MONEY)
    deposit: Decimal = Field(Decimal("0"), ge=0, **MONEY)
    payCycleMonths: int = Field(1, ge=1, le=12)
    advanceDays: int = Field(0, ge=0, le=60)
    occupants: int = Field(1, ge=1, le=20)
    signedDate: date | None = None
    fees: list[FeeChoiceIn] = Field(default_factory=list, max_length=20)
    note: str = Field("", max_length=500)
    inquiryId: int | None = Field(None, gt=0)

    @model_validator(mode="after")
    def _check(self) -> "LeaseSignIn":
        if (self.renterId is None) == (self.newRenter is None):
            raise ValueError("请选择已有租客或填写新租客，二选一")
        if self.endDate < self.startDate:
            raise ValueError("到期日不能早于起租日")
        return self


class LeaseMetaIn(BaseModel):
    occupants: int = Field(ge=1, le=20)
    signedDate: date | None = None
    note: str = Field("", max_length=500)


class ExtraChargeIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    amount: Decimal = Field(gt=0, **MONEY)


class CheckoutIn(BaseModel):
    checkoutDate: date
    extras: list[ExtraChargeIn] = Field(default_factory=list, max_length=20)
    note: str = Field("", max_length=500)


class PayIn(BaseModel):
    amount: Decimal = Field(gt=0, **MONEY)
    method: Literal["cash", "wechat", "alipay", "bank", "other"]
    paidOn: date | None = None
    note: str = Field("", max_length=200)


class DiscountIn(BaseModel):
    amount: Decimal = Field(ge=0, **MONEY)
    note: str | None = Field(None, max_length=200)


class MeterIn(BaseModel):
    feeItemId: int = Field(gt=0)
    reading: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    readDate: date
    prevReading: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
