from typing import Optional
from pydantic import BaseModel


class PermissionCreate(BaseModel):
    name: str
    path: str


class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None


class Permission(BaseModel):
    id: int
    name: str
    path: str

    class Config:
        from_attributes = True


class RolePermissionAssign(BaseModel):
    permission_ids: list[int]
