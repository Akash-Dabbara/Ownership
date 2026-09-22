from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str
    role: str
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str