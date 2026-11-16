from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AnalyzeRequest(BaseModel):
    repo_url: str = Field(examples=["https://github.com/user/smart-resume-analyzer"])


class AskRequest(BaseModel):
    repo_name: str
    question: str = Field(min_length=3, max_length=2000)
