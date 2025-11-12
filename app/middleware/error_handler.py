from fastapi import Request

async def handle_exceptions(request: Request, call_next):
    return await call_next(request)
