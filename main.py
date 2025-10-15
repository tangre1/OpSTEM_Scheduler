# Command needed to run: uvicorn main:app --reload


from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

@app.post("/submit")
async def submit_schedule(request: Request):
    data = await request.json()
    ta_name = data["taName"]
    days = data["days"]
    return {"message": f"Schedule received for {ta_name} on {days}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
