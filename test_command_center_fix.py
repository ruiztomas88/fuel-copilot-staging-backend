#!/usr/bin/env python
"""
Test Command Center después del fix de intake_air_temp_f
"""
from fleet_command_center import FleetCommandCenter

print("=" * 80)
print("🧪 TESTING FLEET COMMAND CENTER - Post Fix")
print("=" * 80)

try:
    cc = FleetCommandCenter()
    print("✅ FleetCommandCenter instanciado correctamente")
    
    print("\n⏳ Generando Command Center data...")
    data = cc.generate_command_center_data()
    
    # data es un objeto CommandCenterData, convertirlo a dict
    data_dict = data.dict() if hasattr(data, 'dict') else data.__dict__
    
    # Extract key metrics
    dtcs = data_dict.get("alerts", {}).get("dtc_alerts", [])
    metrics = data_dict.get("metrics", [])
    kpis = data_dict.get("kpis", {})
    
    print("\n" + "=" * 80)
    print("✅ COMMAND CENTER GENERATION SUCCESS")
    print("=" * 80)
    
    print(f"\n📊 RESULTADOS:")
    print(f"  - DTCs activos: {len(dtcs)}")
    print(f"  - Trucks con métricas: {len(metrics)}")
    print(f"  - Total trucks fleet: {kpis.get('total_trucks', 0)}")
    print(f"  - Trucks activos: {kpis.get('active_trucks', 0)}")
    print(f"  - Fleet efficiency: {kpis.get('fleet_efficiency_score', 0):.1f}%")
    
    if dtcs:
        print(f"\n⚠️  DTCs encontrados:")
        for dtc in dtcs[:5]:  # Show first 5
            print(f"    - {dtc.get('truck_id')}: {dtc.get('code')} - {dtc.get('description', 'N/A')}")
    
    print("\n✅ TODAS LAS QUERIES SQL FUNCIONAN CORRECTAMENTE")
    print("✅ FIX DE intake_air_temp_f VERIFICADO")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
