from pydantic import BaseModel, Field, model_validator

from app.auth.security import MAX_PASSWORD_BYTES
from app.schemas.users import UserOut


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=254, description="Email or roll number")
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @model_validator(mode="after")
    def _differs(self):
        if len(self.new_password.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError("That password is too long. Use a shorter one.")
        if self.new_password == self.current_password:
            raise ValueError("The new password must be different from the current one.")
        return self
