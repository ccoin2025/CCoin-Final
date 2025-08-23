from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    telegram_id: str
    username: Optional[str]

class UserCreate(UserBase):
    first_name: str
    last_name: str

class UserInDB(UserBase):
    id: int
    tokens: int
    wallet_address: Optional[str]

    class Config:
        from_attributes = True