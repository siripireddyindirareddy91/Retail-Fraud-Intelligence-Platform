from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Input):
    email: EmailStr = Field(max_length=254)
    # Password whitespace is intentional, never silently trim it.
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=12, max_length=128)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).casefold()

    @field_validator("password", mode="before")
    @classmethod
    def preserve_password(cls, value):
        return value


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80)


class ProfileUpdate(Input):
    display_name: str = Field(min_length=1, max_length=80)


class SettingsUpdate(Input):
    theme: Literal["light", "dark"] | None = None
    methodology_guidance: bool | None = None
    job_notifications: bool | None = None


class UserUpdate(Input):
    role: Literal["researcher", "administrator"] | None = None
    active: bool | None = None


class JobSubmission(Input):
    kind: Literal["system.integrity_check"] = "system.integrity_check"


class ExperimentCreate(Input):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["robustness", "training", "quality"]
    seed: int = Field(default=42, ge=0, le=2**32-1)


class NotificationUpdate(Input):
    read: Literal[True]
