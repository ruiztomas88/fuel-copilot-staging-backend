"""
Test completo del flujo DTC: Decoder → Alert
Verifica que SPN 523452 (Freightliner) se procese correctamente
"""

from alert_service import send_dtc_alert
from dtc_decoder import FuelCopilotDTCHandler

print("=" * 80)
print("🧪 TEST COMPLETO - DTC DECODER → ALERT")
print("=" * 80)
print()

# Initialize handler
handler = FuelCopilotDTCHandler()

# Process the problematic DTC from DO9693
truck_id = "DO9693"
spn = 523452
fmi = 3

print(f"📋 Processing DTC for truck {truck_id}: SPN{spn}.FMI{fmi}")
print()

# Step 1: Decode DTC
dtc_result = handler.process_wialon_dtc(truck_id=truck_id, spn=spn, fmi=fmi)

print("✅ STEP 1: Decoder Output")
print("-" * 80)
for key, value in dtc_result.items():
    if isinstance(value, str) and len(value) > 100:
        print(f"  {key}: {value[:97]}...")
    else:
        print(f"  {key}: {value}")
print()

# Step 2: Check critical fields for alert
print("✅ STEP 2: Alert-Ready Fields")
print("-" * 80)
print(f"  truck_id: {dtc_result['truck_id']}")
print(f"  dtc_code: {dtc_result['dtc_code']}")
print(f"  system/category: {dtc_result.get('category', 'UNKNOWN')}")
print(f"  severity: {dtc_result['severity']}")
print(f"  description: {dtc_result['description'][:80]}...")
print(f"  oem: {dtc_result['oem']}")
print(f"  spn_explanation: {dtc_result.get('spn_explanation', 'N/A')[:80]}...")
print(f"  fmi_explanation: {dtc_result.get('fmi_explanation', 'N/A')[:80]}...")
print()

# Step 3: Simulate alert (WITHOUT actually sending)
print("✅ STEP 3: Alert Message Preview")
print("-" * 80)

severity_es = "CRÍTICO" if dtc_result["severity"] == "CRITICAL" else "ADVERTENCIA"
emoji = "🚨" if dtc_result["severity"] == "CRITICAL" else "⚠️"
system = dtc_result.get("category", "UNKNOWN")

# Check if we have Spanish explanations
spn_explanation = dtc_result.get("spn_explanation")
fmi_explanation = dtc_result.get("fmi_explanation")

if spn_explanation and fmi_explanation:
    print("✅ Full Spanish description available!")
    print()
    message = (
        f"{emoji} CÓDIGO DE DIAGNÓSTICO DEL MOTOR\n\n"
        f"🔧 Código: {dtc_result['dtc_code']} (SPN {dtc_result['spn']} / FMI {dtc_result['fmi']})\n"
        f"⚙️ Sistema: {system}\n"
        f"📊 Severidad: {severity_es}\n\n"
        f"🔍 Componente: {spn_explanation[:200]}\n"
        f"❌ Falla: {fmi_explanation[:200]}\n\n"
        f"✅ Acción Recomendada:\n{dtc_result['action_required']}"
    )
else:
    print("❌ Fallback to basic description")
    print()
    message = (
        f"{emoji} CÓDIGO DE DIAGNÓSTICO DEL MOTOR\n\n"
        f"🔧 Código: {dtc_result['dtc_code']}\n"
        f"⚙️ Sistema: {system}\n"
        f"📊 Severidad: {severity_es}\n\n"
        f"❌ Descripción: {dtc_result['description']}\n\n"
        f"✅ Acción Recomendada:\n{dtc_result['action_required']}"
    )

print(message)
print()
print("=" * 80)

# Summary
print("📊 RESULT SUMMARY")
print("=" * 80)
if system == "UNKNOWN":
    print("❌ FAILED: System still showing as UNKNOWN")
else:
    print(f"✅ SUCCESS: System = {system}")

if "desconocido" in dtc_result["description"].lower():
    print("❌ FAILED: Description still says 'desconocido'")
else:
    print(f"✅ SUCCESS: Description = {dtc_result['description'][:50]}...")

if dtc_result["oem"] == "Unknown":
    print("❌ FAILED: OEM not detected")
else:
    print(f"✅ SUCCESS: OEM = {dtc_result['oem']}")

print()
print("🎯 EXPECTED:")
print("   - System: Should be 'OEM Proprietary' or similar (NOT 'UNKNOWN')")
print("   - OEM: Should be 'Freightliner/Detroit Diesel'")
print("   - Description: Should mention Freightliner Parameter 523452")
print("=" * 80)
