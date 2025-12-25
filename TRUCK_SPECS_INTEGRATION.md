# 🚛 Truck Specs Integration Guide

This document explains how to use the new `truck_specs` data (VIN-decoded specifications) throughout the Fuel Analytics system.

## 📊 What We Have

**Data Source**: [truck_specs.csv](truck_specs.csv) and `truck_specs` table in MySQL

**38 Active Trucks** with:
- VIN (Vehicle Identification Number)
- Year, Make, Model
- **Baseline MPG Loaded** (expected MPG when hauling 44,000 lbs)
- **Baseline MPG Empty** (expected MPG when empty)
- Age and notes

### Fleet Summary:
- **Kenworth**: 17 trucks, 6.72 MPG loaded avg
- **Freightliner**: 8 trucks, 5.88 MPG loaded avg
- **International**: 7 trucks, 6.63 MPG loaded avg
- **Peterbilt**: 4 trucks, 6.5 MPG loaded avg
- **Volvo**: 2 trucks, 6.65 MPG loaded avg

**Fleet Average**: 6.5 MPG loaded, 8.18 MPG empty, 9 years old

---

## 🚀 5 Ways to Use This Data

### 1. **MPG Validation with Truck-Specific Baselines**

**OLD WAY** (generic):
```python
def validate_mpg(mpg: float) -> bool:
    return 3.5 <= mpg <= 9.0  # Same for all trucks
```

**NEW WAY** (truck-specific):
```python
from truck_specs_engine import validate_truck_mpg

result = validate_truck_mpg('MR7679', current_mpg=5.5, is_loaded=True)
# Returns:
# {
#   'status': 'WARNING',
#   'expected_mpg': 6.8,
#   'current_mpg': 5.5,
#   'deviation_pct': -19.1,
#   'message': 'MPG 5.5 below baseline 6.8 (-19.1%)'
# }
```

**Benefits**:
- ✅ Each truck validated against its own baseline
- ✅ 2017 Freightliner (6.8 MPG) vs 2006 Freightliner (5.0 MPG) have different expectations
- ✅ Loaded vs Empty baselines

See: [examples/example_1_mpg_validation.py](examples/example_1_mpg_validation.py)

---

### 2. **Smart Alerts Based on Truck Performance**

Generate alerts when trucks underperform **their specific baseline**, not the fleet average.

```python
from truck_specs_engine import validate_truck_mpg

# MR7679 = 2017 Freightliner Cascadia (baseline: 6.8 MPG loaded)
result = validate_truck_mpg('MR7679', 4.0, is_loaded=True)

if result['status'] == 'CRITICAL':
    send_alert(f"⚠️ {truck_id} performing 41% below baseline!")
```

**Alert Tiers**:
- 🟢 **GOOD**: MPG ≥ baseline (0% or better)
- 🔵 **NORMAL**: -12.5% to 0% below baseline
- 🟡 **WARNING**: -25% to -12.5% below baseline
- 🔴 **CRITICAL**: < -25% below baseline

See: [examples/example_2_smart_alerts.py](examples/example_2_smart_alerts.py)

---

### 3. **Fleet Analytics by Make/Model/Year**

Compare performance across different truck types:

```python
from examples.example_3_fleet_analytics import analyze_fleet_by_make

analyze_fleet_by_make()
# Output:
# Make            Trucks   Expected   Actual     Deviation    Status
# ============================================================================
# Kenworth        15       6.72       6.45       -4.0%        ✓ GOOD
# Freightliner    7        5.88       5.20       -11.6%       ✓ GOOD
# International   6        6.63       6.80       +2.6%        ✅ EXCEEDS
```

**Use Cases**:
- Compare manufacturers (Kenworth vs Freightliner)
- Identify underperforming models
- Track MPG degradation by truck age
- Benchmark similar trucks

See: [examples/example_3_fleet_analytics.py](examples/example_3_fleet_analytics.py)

---

### 4. **API Endpoints for Frontend**

Expose truck specs through your FastAPI:

```python
# Add to api_v2.py or main.py:
from examples.example_4_api_endpoints import router as truck_specs_router
app.include_router(truck_specs_router)
```

**Available Endpoints**:

| Endpoint | Description |
|----------|-------------|
| `GET /api/truck-specs/` | All truck specs |
| `GET /api/truck-specs/{truck_id}` | Specs for one truck |
| `POST /api/truck-specs/{truck_id}/validate-mpg` | Validate current MPG |
| `GET /api/truck-specs/fleet/stats` | Fleet statistics |
| `GET /api/truck-specs/{truck_id}/similar` | Find similar trucks (same make/model) |

**Example**:
```bash
curl "http://localhost:8000/api/truck-specs/MR7679"
# Returns:
# {
#   "truck_id": "MR7679",
#   "year": 2017,
#   "make": "Freightliner",
#   "model": "Cascadia",
#   "baseline_mpg_loaded": 6.8,
#   "baseline_mpg_empty": 8.8,
#   "expected_range": [6.8, 8.8],
#   "age_years": 8
# }
```

See: [examples/example_4_api_endpoints.py](examples/example_4_api_endpoints.py)

---

### 5. **Frontend Dashboard Component**

Display truck MPG performance vs baseline in React:

```tsx
import TruckMPGComparison from '@/components/TruckMPGComparison';

// Shows:
// - Summary cards (how many trucks exceeding, normal, warning, critical)
// - Detailed table with current MPG vs expected MPG
// - Color-coded status indicators
// - Deviation percentages
```

**Features**:
- ✅ Visual comparison: Current vs Expected MPG
- ✅ Status badges (GOOD, NORMAL, WARNING, CRITICAL)
- ✅ Sortable by deviation (worst performers first)
- ✅ Filterable by make, model, year
- ✅ Dark mode support

See: [examples/example_5_frontend_component.py](examples/example_5_frontend_component.py)

---

## 🔧 Implementation Steps

### Step 1: Install the engine
The engine is already created at [truck_specs_engine.py](truck_specs_engine.py)

Test it:
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend
source venv/bin/activate
python truck_specs_engine.py
```

### Step 2: Use in wialon_sync_enhanced.py

Add truck-specific validation when calculating MPG:

```python
from truck_specs_engine import validate_truck_mpg

# After calculating MPG
if mpg_current:
    result = validate_truck_mpg(truck_id, mpg_current, is_loaded=True)
    
    if result['status'] == 'CRITICAL':
        logger.warning(f"⚠️ {truck_id}: {result['message']}")
    
    # Store validation info
    metrics_data['mpg_status'] = result['status']
    metrics_data['mpg_deviation_pct'] = result['deviation_pct']
    metrics_data['expected_mpg'] = result['expected_mpg']
```

### Step 3: Update alert_service.py

Use truck-specific baselines for MPG alerts:

```python
from truck_specs_engine import get_expected_mpg

# OLD
if mpg_current < 4.5:  # Generic threshold
    create_alert("Low MPG")

# NEW
expected_mpg = get_expected_mpg(truck_id, is_loaded=True)
if expected_mpg and mpg_current < (expected_mpg * 0.75):  # 25% below baseline
    create_alert(f"Low MPG: {mpg_current:.1f} vs {expected_mpg:.1f} expected")
```

### Step 4: Add API endpoints

```python
# In api_v2.py or main.py
from examples.example_4_api_endpoints import router as truck_specs_router

app.include_router(truck_specs_router)
```

### Step 5: Create frontend component

1. Copy TypeScript code from `examples/example_5_frontend_component.py`
2. Create file: `src/components/TruckMPGComparison.tsx`
3. Add route in your router
4. Add navigation link

---

## 📈 Expected Benefits

1. **More Accurate Alerts**
   - Stop alerting on 2006 trucks with 5.2 MPG (that's normal for them!)
   - Alert on 2023 trucks with 6.0 MPG (should be 7.8 MPG)

2. **Better Benchmarking**
   - Compare apples to apples (same make/model)
   - Track degradation over time
   - Identify maintenance needs

3. **Fleet Insights**
   - Which manufacturer performs best?
   - Should we buy more Kenworth or Freightliner?
   - ROI on newer trucks (7.8 MPG) vs older (5.0 MPG)

4. **Driver Performance**
   - Fair comparison (driver in 2023 truck vs driver in 2006 truck)
   - Incentivize drivers who exceed their truck's baseline

5. **Maintenance Planning**
   - Trucks significantly below baseline may need service
   - Track MPG degradation as early warning

---

## 🧪 Testing

Run all examples:
```bash
cd /Users/tomasruiz/Desktop/Fuel-Analytics-Backend

# Test the engine
python truck_specs_engine.py

# Test MPG validation
python examples/example_1_mpg_validation.py

# Test smart alerts
python examples/example_2_smart_alerts.py

# Test fleet analytics (requires database with recent metrics)
python examples/example_3_fleet_analytics.py
```

---

## 📝 Next Steps

1. **Integrate into wialon_sync_enhanced.py**
   - Add `validate_truck_mpg()` calls after MPG calculation
   - Store deviation_pct in fuel_metrics table

2. **Update alert_service.py**
   - Replace generic MPG thresholds with truck-specific baselines
   - Create "Underperforming vs Baseline" alert type

3. **Add API endpoints**
   - Expose truck specs to frontend
   - Add validation endpoint

4. **Create frontend components**
   - Truck MPG comparison dashboard
   - Add "Expected MPG" column to truck list
   - Show deviation badges

5. **Database schema updates** (optional)
   ```sql
   ALTER TABLE fuel_metrics 
   ADD COLUMN expected_mpg DECIMAL(5,2),
   ADD COLUMN mpg_deviation_pct DECIMAL(6,2),
   ADD COLUMN mpg_status VARCHAR(20);
   ```

---

## 🎯 Quick Win Example

**Immediate improvement**: Update your KPIs page to show fleet baseline from `truck_specs` instead of hardcoded 5.7:

```python
# OLD (api_v2.py):
baseline_mpg = 5.7

# NEW:
from truck_specs_engine import get_truck_specs_engine
engine = get_truck_specs_engine()
stats = engine.get_fleet_stats()
baseline_mpg = stats['fleet_avg_mpg_loaded']  # 6.5 MPG (more accurate!)
```

This alone will make your MPG gap calculations more realistic! 🎉

---

## 📚 Files Created

- ✅ `truck_specs.csv` - VIN-decoded data for 38 trucks
- ✅ `create_truck_specs_table.sql` - Database schema + data
- ✅ `truck_specs_engine.py` - Core engine for truck specs
- ✅ `examples/example_1_mpg_validation.py` - MPG validation examples
- ✅ `examples/example_2_smart_alerts.py` - Smart alert system
- ✅ `examples/example_3_fleet_analytics.py` - Fleet analytics
- ✅ `examples/example_4_api_endpoints.py` - FastAPI endpoints
- ✅ `examples/example_5_frontend_component.py` - React component
- ✅ `TRUCK_SPECS_INTEGRATION.md` - This guide

---

**Questions?** Review the examples in the `examples/` folder or test the engine with `python truck_specs_engine.py`
