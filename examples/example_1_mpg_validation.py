"""
Example 1: Enhanced MPG Validation using truck_specs

Instead of generic 5.7 MPG baseline, use truck-specific baselines
"""

from truck_specs_engine import validate_truck_mpg


# OLD WAY (generic baseline)
def old_validate_mpg(truck_id: str, mpg: float) -> bool:
    return 3.5 <= mpg <= 9.0  # Generic range


# NEW WAY (truck-specific baseline)
def new_validate_mpg(truck_id: str, mpg: float, is_loaded: bool = True) -> dict:
    result = validate_truck_mpg(truck_id, mpg, is_loaded)

    print(f"🚛 {truck_id}: {result['truck_info']}")
    print(f"   Current MPG: {result['current_mpg']:.1f}")
    print(f"   Expected: {result['expected_mpg']:.1f}")
    print(f"   Deviation: {result['deviation_pct']:+.1f}%")
    print(f"   Status: {result['status']}")
    print(f"   {result['message']}")

    return result


# Example usage
if __name__ == "__main__":
    # MR7679 = 2017 Freightliner Cascadia (baseline: 6.8 loaded, 8.8 empty)
    print("LOADED scenarios:")
    new_validate_mpg("MR7679", 5.5, is_loaded=True)  # WARNING: -19%
    print()
    new_validate_mpg("MR7679", 6.8, is_loaded=True)  # GOOD: 0%
    print()
    new_validate_mpg("MR7679", 4.0, is_loaded=True)  # CRITICAL: -41%

    print("\n" + "=" * 60)
    print("EMPTY scenarios:")
    new_validate_mpg("MR7679", 8.5, is_loaded=False)  # NORMAL
    print()
    new_validate_mpg("MR7679", 6.0, is_loaded=False)  # WARNING (should be 8.8 empty)
