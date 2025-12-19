"""
Test directo del endpoint /api/v2/trucks/{truck_id}
Para verificar que ahora retorna datos correctos
"""
import requests
import json

truck_id = "DO9693"
base_url = "http://localhost:8000"

print("=" * 80)
print(f"🔍 PROBANDO ENDPOINT: /fuelAnalytics/api/v2/trucks/{truck_id}")
print("=" * 80)

try:
    # Test truck detail endpoint
    url = f"{base_url}/fuelAnalytics/api/v2/trucks/{truck_id}"
    print(f"\n📡 GET {url}")
    
    response = requests.get(url, timeout=10)
    
    print(f"\n📊 Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ RESPUESTA EXITOSA:")
        print(f"   truck_id: {data.get('truck_id')}")
        print(f"   timestamp: {data.get('timestamp')}")
        print(f"   truck_status: {data.get('truck_status')}")
        print(f"   estimated_pct: {data.get('estimated_pct')}")
        print(f"   mpg_current: {data.get('mpg_current')}")
        print(f"   speed_mph: {data.get('speed_mph')}")
        print(f"   rpm: {data.get('rpm')}")
        print(f"\n📦 Total fields: {len(data.keys())}")
        
        # Check for N/A values
        na_fields = [k for k, v in data.items() if v == "N/A" or v is None]
        if na_fields:
            print(f"\n⚠️  Campos N/A o None ({len(na_fields)}): {na_fields[:10]}...")
        else:
            print(f"\n✅ No hay campos N/A!")
    else:
        print(f"\n❌ ERROR {response.status_code}: {response.text[:200]}")
        
except requests.exceptions.ConnectionError:
    print(f"\n❌ ERROR: No se pudo conectar a {base_url}")
    print(f"   ¿Está corriendo el servidor FastAPI?")
    print(f"\n💡 Para iniciar el servidor:")
    print(f"   cd C:\\Users\\devteam\\Proyectos\\fuel-analytics-backend")
    print(f"   .\\venv\\Scripts\\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
