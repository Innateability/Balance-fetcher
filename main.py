from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "✅ Bot is running. Use POST /signal to send a signal."}

@app.post("/signal")
async def receive_signal(request: Request):
    try:
        data = await request.json()
        print("🚨 Received signal from Zapier:", data)
        return {"status": "success", "received": data}
    except Exception as e:
        print("⚠️ Error receiving signal:", e)
        return {"status": "error", "message": str(e)}

# If running locally, uncomment below
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)
