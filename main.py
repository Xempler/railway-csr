from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import asyncpg
import json
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Railway CSR Dashboard",
    description="FastAPI server for Railway Customer Service Representative Dashboard",
    version="1.0.0"
)

# Database configuration
DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "railway.c7iocu4wmxh2.ap-southeast-1.rds.amazonaws.com"),
    "port": os.getenv("DB_PORT", 5432),
    "database": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "abcd1234")
}

# Database connection pool
db_pool = None

async def init_db():
    """Initialize database connection pool"""
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"],
            database=DATABASE_CONFIG["database"],
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            min_size=1,
            max_size=10
        )
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        raise

async def close_db():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_db()

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown"""
    await close_db()

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
async def get_data():
    """Serve the data.json file"""
    return FileResponse("data.json", media_type="application/json")


@app.get("/data_1.json")
async def get_data_1():
    """Fetch data from PostgreSQL database and enrich data.json with status and company"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        # First, read the existing data.json file
        try:
            with open("data.json", "r", encoding="utf-8") as file:
                static_data = json.load(file)
        except FileNotFoundError:
            logger.error("data.json file not found")
            raise HTTPException(status_code=404, detail="data.json file not found")
        
        # Fetch database results
        async with db_pool.acquire() as connection:
            # Join Stations and Users tables
            stations_query = """
                SELECT 
                    s.id,
                    s.name,
                    s.status,
                    u.company
                FROM public."Stations" s
                LEFT JOIN public."Users" u ON s.blocked_by = u.mobile
                ORDER BY s.id;
            """
            
            # Join Gates and Users tables
            gates_query = """
                SELECT 
                    g.id,
                    g.gate_name,
                    g.status,
                    g.section,
                    g.district,
                    g.blocked_until,
                    g.confirmed,
                    u.company
                FROM public."Gates" g
                LEFT JOIN public."Users" u ON g.blocked_by = u.mobile
                ORDER BY g.id;
            """
            
            # Fetch stations data
            stations_rows = await connection.fetch(stations_query)
            
            # Convert database rows to dictionary with id as key for easy lookup
            db_data = {}
            for row in stations_rows:
                row_dict = dict(row)
                # Convert datetime objects to strings for JSON serialization
                for key, value in row_dict.items():
                    if hasattr(value, 'isoformat'):
                        row_dict[key] = value.isoformat()
                db_data[row_dict['id']] = row_dict
            
            # Fetch gates data
            try:
                gates_rows = await connection.fetch(gates_query)
                gates_data = []
                for row in gates_rows:
                    row_dict = dict(row)
                    # Convert datetime objects to strings for JSON serialization
                    for key, value in row_dict.items():
                        if hasattr(value, 'isoformat'):
                            row_dict[key] = value.isoformat()
                    gates_data.append(row_dict)
                
                logger.info(f"Successfully fetched {len(db_data)} stations and {len(gates_data)} gates from database")
            except asyncpg.exceptions.UndefinedTableError:
                logger.warning("Gates table not found, proceeding with stations only")
                gates_data = []
            
            # Enrich the static data with database results
            enriched_data = json.loads(json.dumps(static_data))  # Deep copy
            
            # Enrich stations
            if 'stations' in enriched_data:
                for station in enriched_data['stations']:
                    station_id = station.get('id')
                    if station_id and station_id in db_data:
                        db_station = db_data[station_id]
                        # Add status if not null and not already present
                        if db_station.get('status') and 'status' not in station:
                            station['status'] = db_station['status']
                        # Add company if not null and not already present
                        if db_station.get('company') and 'company' not in station:
                            station['company'] = db_station['company']
                        # Update existing status/company if database has non-null values
                        elif db_station.get('status'):
                            station['status'] = db_station['status']
                        elif db_station.get('company'):
                            station['company'] = db_station['company']
            
            # Enrich cross-gates if they exist in database
            if 'cross-gates' in enriched_data:
                for gate in enriched_data['cross-gates']:
                    gate_id = gate.get('id')
                    if gate_id and gate_id in db_data:
                        db_gate = db_data[gate_id]
                        # Add status if not null and not already present
                        if db_gate.get('status') and 'status' not in gate:
                            gate['status'] = db_gate['status']
                        # Add company if not null and not already present  
                        if db_gate.get('company') and 'company' not in gate:
                            gate['company'] = db_gate['company']
                        # Update existing status/company if database has non-null values
                        elif db_gate.get('status'):
                            gate['status'] = db_gate['status']
                        elif db_gate.get('company'):
                            gate['company'] = db_gate['company']
            
            # Add gates data from database to cross-gates array in the same format
            if 'cross-gates' not in enriched_data:
                enriched_data['cross-gates'] = []
            
            for gate in gates_data:
                formatted_gate = {
                    "id": gate['id'],
                    "name": gate['gate_name']
                }
                # Add status if not null
                if gate.get('status'):
                    formatted_gate['status'] = gate['status']
                # Add company if not null
                if gate.get('company'):
                    formatted_gate['company'] = gate['company']
                # Add additional fields if needed
                if gate.get('section'):
                    formatted_gate['section'] = gate['section']
                if gate.get('district'):
                    formatted_gate['district'] = gate['district']
                if gate.get('blocked_until'):
                    formatted_gate['blocked_until'] = gate['blocked_until']
                if gate.get('confirmed') is not None:
                    formatted_gate['confirmed'] = gate['confirmed']
                
                enriched_data['cross-gates'].append(formatted_gate)
            
            logger.info("Successfully enriched data.json with database results")
            return enriched_data
            
    except asyncpg.exceptions.UndefinedTableError as e:
        # If the database table doesn't exist, return original data.json
        logger.warning(f"Database table not found: {e}, returning original data.json")
        try:
            with open("data.json", "r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return {"error": "Both database tables and data.json file not found"}
            
    except Exception as e:
        logger.error(f"Error enriching data: {e}")
        raise HTTPException(status_code=500, detail=f"Error enriching data: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if db_pool else "disconnected"
    return {
        "status": "healthy", 
        "message": "Railway CSR Dashboard is running",
        "database": db_status
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 