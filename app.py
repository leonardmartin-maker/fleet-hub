import os
from app.main import app

PORT = int(os.getenv("PORT", "8002"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=False)