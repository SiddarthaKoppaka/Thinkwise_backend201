from pydantic import BaseModel

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
