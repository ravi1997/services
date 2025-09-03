def success(message: str, data: dict | list | None = None, status_code: int = 200):
    body = {
        "status": "success",
        "message": message,
        "data": data if data is not None else {},
    }
    return body, status_code


def error(message: str, error_code: str, status_code: int = 400, data: dict | None = None):
    body = {
        "status": "error",
        "message": message,
        "data": {"error_code": error_code} | (data or {}),
    }
    return body, status_code

