def success(message: str, data: dict | list | None = None, status_code: int = 200):
    body = {
        "status": "success",
        "message": message,
        "data": data if data is not None else {},
        "code": status_code
    }
    return body, status_code

def error(message: str, error_code: str, status_code: int = 400, data: dict | None = None, internal: str = None):
    # Mask internal info in error responses
    masked_message = message
    if internal:
        # Don't expose internal details in the response
        masked_message = f"{message} (see logs for details)"
    
    response_data = {"error_code": error_code}
    if data:
        # Only include explicitly allowed fields in error response
        response_data.update(data)
    
    body = {
        "status": "error",
        "message": masked_message,
        "data": response_data,
        "code": status_code
    }
    return body, status_code

