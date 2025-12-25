"""
Example 4: API Endpoint to expose truck specs

Add this to your FastAPI app (api_v2.py or main.py)
"""

from fastapi import APIRouter, HTTPException

from truck_specs_engine import get_truck_specs_engine, validate_truck_mpg

router = APIRouter(prefix="/api/truck-specs", tags=["Truck Specs"])


@router.get("/")
def get_all_truck_specs():
    """Get specs for all trucks"""
    engine = get_truck_specs_engine()
    return {
        truck_id: {
            "vin": specs.vin,
            "year": specs.year,
            "make": specs.make,
            "model": specs.model,
            "baseline_mpg_loaded": specs.baseline_mpg_loaded,
            "baseline_mpg_empty": specs.baseline_mpg_empty,
            "age_years": specs.age_years,
            "notes": specs.notes,
        }
        for truck_id, specs in engine._specs_cache.items()
    }


@router.get("/{truck_id}")
def get_truck_specs(truck_id: str):
    """Get specs for a specific truck"""
    engine = get_truck_specs_engine()
    specs = engine.get_specs(truck_id)

    if not specs:
        raise HTTPException(status_code=404, detail=f"Truck {truck_id} not found")

    return {
        "truck_id": specs.truck_id,
        "vin": specs.vin,
        "year": specs.year,
        "make": specs.make,
        "model": specs.model,
        "baseline_mpg_loaded": specs.baseline_mpg_loaded,
        "baseline_mpg_empty": specs.baseline_mpg_empty,
        "expected_range": specs.expected_mpg_range,
        "age_years": specs.age_years,
        "notes": specs.notes,
    }


@router.post("/{truck_id}/validate-mpg")
def validate_mpg_endpoint(truck_id: str, current_mpg: float, is_loaded: bool = True):
    """Validate current MPG against truck baseline"""
    result = validate_truck_mpg(truck_id, current_mpg, is_loaded)
    return result


@router.get("/fleet/stats")
def get_fleet_stats():
    """Get fleet-wide statistics"""
    engine = get_truck_specs_engine()
    return engine.get_fleet_stats()


@router.get("/{truck_id}/similar")
def get_similar_trucks(truck_id: str):
    """Get trucks with similar specs (same make/model)"""
    engine = get_truck_specs_engine()
    similar = engine.get_similar_trucks(truck_id)

    if not similar:
        return {"message": f"No similar trucks found for {truck_id}"}

    return {
        "truck_id": truck_id,
        "similar_trucks": [
            {
                "truck_id": s.truck_id,
                "year": s.year,
                "baseline_mpg_loaded": s.baseline_mpg_loaded,
                "baseline_mpg_empty": s.baseline_mpg_empty,
                "age_years": s.age_years,
            }
            for s in similar
        ],
    }


# Example usage in your main app:
#
# from examples.example_4_api_endpoints import router as truck_specs_router
# app.include_router(truck_specs_router)
#
# Then you can call:
# GET  /api/truck-specs/
# GET  /api/truck-specs/MR7679
# POST /api/truck-specs/MR7679/validate-mpg?current_mpg=5.5&is_loaded=true
# GET  /api/truck-specs/fleet/stats
# GET  /api/truck-specs/MR7679/similar
