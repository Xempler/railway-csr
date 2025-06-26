from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title="Railway CSR Dashboard",
    description="FastAPI server for Railway Customer Service Representative Dashboard",
    version="1.0.0"
)

# Mount static files directory for images and other assets
if os.path.exists("img"):
    app.mount("/img", StaticFiles(directory="img"), name="img")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main index.html file at the root URL"""
    try:
        with open("index.html", "r", encoding="utf-8") as file:
            content = file.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: index.html not found</h1>", status_code=404)

@app.get("/data.json")
async def get_stations():
    """Serve the stations.json file"""
    return FileResponse("data.json", media_type="application/json")

@app.get("/Station-list.json")
async def get_station_list():
    """Serve the Station-list.json file"""
    return FileResponse("Station-list.json", media_type="application/json")

@app.get("/bought-stations.json")
async def get_bought_stations():
    """Serve the bought-stations.json file"""
    return FileResponse("bought-stations.json", media_type="application/json")

@app.get("/cross-gates.json")
async def get_cross_gates():
    """Serve the cross-gates.json file"""
    return FileResponse("cross-gates.json", media_type="application/json")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Railway CSR Dashboard is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 