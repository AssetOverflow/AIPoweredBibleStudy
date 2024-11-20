from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def health_check():
    return {"message": "Bible Study Chat API is running smoothly!"}