import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # Run uvicorn on localhost with hot reloading
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
