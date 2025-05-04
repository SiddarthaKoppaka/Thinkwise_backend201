from pydantic import BaseModel
from pydantic.networks import EmailStr

class UserRegister(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserProfile(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class UserOut(Token):
    email: str
    first_name: str
    last_name: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str


class SingleIdea(BaseModel):
    title: str
    author: str = ""
    category: str = "Uncategorized"
    description: str
    timestamp: str | None = None