"""房东后台与平台管理的请求体。字段名与前端一致（camelCase），to_db() 转成数据库列。"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PHONE_RE = re.compile(r"^1\d{10}$")
MAX_TAGS = 10


def _check_phone(value: str | None) -> str | None:
    value = value.strip() if value else None
    if value and not PHONE_RE.fullmatch(value):
        raise ValueError("联系电话格式不正确")
    return value or None


class EstateIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    city: str = Field(min_length=1, max_length=20)
    district: str = Field(min_length=1, max_length=20)
    address: str = Field("", max_length=120)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    @field_validator("name", "city", "district", "address")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _non_blank(self) -> "EstateIn":
        if not self.name or not self.city or not self.district:
            raise ValueError("小区名、城市、区域不能为空")
        return self

    def to_db(self) -> dict[str, Any]:
        return self.model_dump()


class ListingIn(BaseModel):
    estateId: int = Field(gt=0)
    rentType: Literal["long", "short", "shared"]
    title: str = Field(min_length=1, max_length=80)
    description: str = Field("", max_length=2000)
    building: str = Field("", max_length=20)
    unitNo: str = Field("", max_length=20)
    bedrooms: int = Field(1, ge=0, le=20)
    halls: int = Field(0, ge=0, le=10)
    baths: int = Field(1, ge=0, le=10)
    area: float = Field(gt=0, le=10000)
    floor: int | None = Field(None, ge=-5, le=200)
    totalFloors: int | None = Field(None, ge=1, le=200)
    orientation: str = Field("", max_length=10)
    priceMonth: int | None = Field(None, gt=0, le=1_000_000)
    priceNight: int | None = Field(None, gt=0, le=100_000)
    depositMonths: int = Field(1, ge=0, le=12)
    minMonths: int = Field(1, ge=1, le=60)
    minNights: int = Field(1, ge=1, le=365)
    tags: list[str] = Field(default_factory=list)
    availableFrom: date | None = None

    @field_validator("title", "description", "building", "unitNo", "orientation")
    @classmethod
    def _trim(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def _tags(cls, tags: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(t.strip() for t in tags if t and t.strip()))
        if len(cleaned) > MAX_TAGS or any(len(t) > 12 for t in cleaned):
            raise ValueError(f"最多 {MAX_TAGS} 个标签，每个不超过 12 字")
        return cleaned

    @model_validator(mode="after")
    def _consistent(self) -> "ListingIn":
        if not self.title:
            raise ValueError("标题不能为空")
        if self.rentType == "short" and self.priceNight is None:
            raise ValueError("短租需要填写每晚价格")
        if self.rentType != "short" and self.priceMonth is None:
            raise ValueError("长租/合租需要填写月租金")
        if self.floor is not None and self.totalFloors is not None and self.floor > self.totalFloors:
            raise ValueError("所在楼层不能高于总楼层")
        return self

    def to_db(self) -> dict[str, Any]:
        return {
            "estate_id": self.estateId, "rent_type": self.rentType, "title": self.title, "description": self.description,
            "building": self.building, "unit_no": self.unitNo, "bedrooms": self.bedrooms, "halls": self.halls,
            "baths": self.baths, "area": self.area, "floor": self.floor, "total_floors": self.totalFloors,
            "orientation": self.orientation, "price_month": self.priceMonth, "price_night": self.priceNight,
            "deposit_months": self.depositMonths, "min_months": self.minMonths, "min_nights": self.minNights,
            "tags": self.tags, "available_from": self.availableFrom,
        }


class StatusIn(BaseModel):
    status: Literal["published", "offline"]


class ImageOrderIn(BaseModel):
    imageIds: list[int] = Field(min_length=1, max_length=50)


class BlockIn(BaseModel):
    start: date
    end: date
    note: str = Field("", max_length=100)

    @model_validator(mode="after")
    def _range(self) -> "BlockIn":
        if self.end <= self.start:
            raise ValueError("结束日期必须晚于开始日期")
        if (self.end - self.start).days > 3 * 366:
            raise ValueError("时段过长")
        return self


class InquiryUpdateIn(BaseModel):
    status: Literal["new", "contacted", "closed"]
    note: str | None = Field(None, max_length=500)


class MemberIn(BaseModel):
    account: str = Field(min_length=3, max_length=120, description="已注册账号的邮箱或手机号")
    role: Literal["owner", "staff"] = "staff"


class LandlordCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    contactName: str | None = Field(None, max_length=20)
    contactPhone: str | None = None
    ownerAccount: str = Field(min_length=3, max_length=120)

    @field_validator("contactPhone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        return _check_phone(value)


class LandlordUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=40)
    contactName: str | None = Field(None, max_length=20)
    contactPhone: str | None = None
    status: Literal["active", "disabled"] | None = None

    @field_validator("contactPhone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        return _check_phone(value)

    def to_db(self) -> dict[str, Any]:
        mapping = {"name": "name", "contactName": "contact_name", "contactPhone": "contact_phone", "status": "status"}
        return {mapping[k]: v for k, v in self.model_dump(exclude_unset=True).items()}


class ModerateIn(BaseModel):
    status: Literal["offline"] | None = None
    recommended: bool | None = None
