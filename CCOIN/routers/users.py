from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.post("/register")
async def register_user():
    raise HTTPException(status_code=403, detail="User registration is only allowed via Telegram webhook")