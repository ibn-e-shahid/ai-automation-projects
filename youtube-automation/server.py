from fastapi import FastAPI
import subprocess
import os

app = FastAPI()

@app.get("/run")
async def run_pipeline():
    try:
        # pipeline.py + merge_fixed.py sequentially run karo
        subprocess.Popen(
            ["D:\\python.exe", "E:\\shorts_pipeline\\run_all.py"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        return {"status": "started", "message": "Pipeline chal rahi hai!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health():
    return {"status": "ok"}