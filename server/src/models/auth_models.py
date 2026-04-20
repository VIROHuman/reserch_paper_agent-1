from pydantic import BaseModel, EmailStr
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class User(BaseModel):
    email: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    is_active: bool = False

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class OTPVerify(BaseModel):
    email: str
    otp: str
