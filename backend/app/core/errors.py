from fastapi import HTTPException


class APIError(HTTPException):
    def __init__(self, status: int, code: str, message: str, details=None, headers=None):
        super().__init__(status, detail={"code": code, "message": message, "details": details}, headers=headers)
