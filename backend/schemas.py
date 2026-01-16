from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List

# Auth Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str
    company_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: int
    client_id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class ApiKeyBase(BaseModel):
    name: str

class ApiKeyCreate(ApiKeyBase):
    pass

class ApiKey(ApiKeyBase):
    id: int
    key: str
    user_id: int
    client_id: int
    created_at: datetime
    last_used: Optional[datetime]
    is_active: bool
    
    class Config:
        from_attributes = True

# Client Schemas
class ClientBase(BaseModel):
    name: str
    company_name: str
    email: EmailStr

class ClientCreate(ClientBase):
    pass

class Client(ClientBase):
    id: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# Document Schemas (with user_id)
class DocumentBase(BaseModel):
    title: str
    content: str

class DocumentCreate(DocumentBase):
    pass

class Document(DocumentBase):
    id: int
    client_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ---- User file schemas ----
class UserFileBase(BaseModel):
    title: str
    tags: Optional[str] = None
    is_public: bool = False


class UserFileCreate(BaseModel):
    title: str
    tags: Optional[str] = None
    is_public: bool = False
    # Le fichier sera envoyé via FormData


class UserFileUpdate(BaseModel):
    title: Optional[str] = None
    tags: Optional[str] = None
    is_public: Optional[bool] = None


class UserFileMetadata(UserFileBase):
    id: int
    filename: str
    original_filename: Optional[str] = None
    file_path: str
    client_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    file_size: int
    mime_type: str
    
    class Config:
        from_attributes = True


class UserFileContent(BaseModel):
    id: int
    title: str
    content: str
    filename: str
    user_id: int
    created_at: datetime
    tags: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserStorageStats(BaseModel):
    user_id: int
    client_id: int
    file_count: int
    total_size_bytes: int
    total_size_mb: float
    storage_path: str
