from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/test")
def read_test():
    return {"Test": "Success"}

if __name__ == "__main__":
    print("Starting simple test server on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)
