import uvicorn

if __name__ == "__main__":
    try:
        uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)
    except KeyboardInterrupt:
        print("👋 Gracefully shutting down...")
