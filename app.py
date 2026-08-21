from fastapi import FastAPI

app = FastAPI()

@app.get("/predict")
def predict(x: float):
    return {"prediction": x * 2}     # our "model" :)

@app.get("/health")
def health():
    return {"status": "ok"}          # remember HEALTHCHECK? this is its target!