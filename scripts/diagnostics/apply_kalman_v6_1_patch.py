"""
Patch para actualizar estimator.py a v6.1.0

Aplica las 3 mejoras críticas de producción:
1. Sensor bias detection
2. Adaptive R basado en consistencia
3. Biodiesel correction

Usage:
    python apply_kalman_v6_1_patch.py

Author: Fuel Copilot Team
Date: December 29, 2025
"""

import re
import sys
from pathlib import Path

ESTIMATOR_FILE = Path(__file__).parent / "estimator.py"

# Verificar que el archivo existe
if not ESTIMATOR_FILE.exists():
    print(f"❌ No se encontró {ESTIMATOR_FILE}")
    sys.exit(1)

print(f"📝 Leyendo {ESTIMATOR_FILE}...")
with open(ESTIMATOR_FILE, "r", encoding="utf-8") as f:
    content = f.read()

changes_made = []

# ═══════════════════════════════════════════════════════════════════════════════
# CAMBIO 1: Agregar imports necesarios (collections.deque)
# ═══════════════════════════════════════════════════════════════════════════════

if "from collections import deque" not in content:
    # Buscar la línea de imports
    import_pattern = r"(import logging\nfrom dataclasses import dataclass)"
    replacement = r"import logging\nfrom collections import deque\nfrom dataclasses import dataclass"

    content = re.sub(import_pattern, replacement, content)
    changes_made.append("✅ Agregado import deque")
else:
    print("⏭️  deque ya importado")

# ═══════════════════════════════════════════════════════════════════════════════
# CAMBIO 2: Agregar atributos de bias detection y biodiesel en __init__
# ═══════════════════════════════════════════════════════════════════════════════

if "self.innovation_history" not in content:
    # Buscar el final de __init__ donde están los sensor quality attributes
    init_pattern = r"(self\.sensor_quality_factor = 1\.0  # Combined quality factor)"

    replacement = r"""\1

        # 🆕 v6.1.0: Sensor bias detection (production feedback)
        self.innovation_history = deque(maxlen=5)
        self.bias_detected = False
        self.bias_magnitude = 0.0

        # 🆕 v6.1.0: Biodiesel correction (optional)
        self.biodiesel_blend_pct = config.get('biodiesel_blend_pct', 0.0)
        self.biodiesel_correction = self._get_biodiesel_correction(self.biodiesel_blend_pct)"""

    content = re.sub(init_pattern, replacement, content)
    changes_made.append("✅ Agregados atributos de bias detection y biodiesel")
else:
    print("⏭️  Atributos de bias detection ya existen")

# ═══════════════════════════════════════════════════════════════════════════════
# CAMBIO 3: Agregar método _get_biodiesel_correction antes de initialize
# ═══════════════════════════════════════════════════════════════════════════════

if "_get_biodiesel_correction" not in content:
    # Buscar el método initialize
    init_method_pattern = r"(    def initialize\(self, fuel_lvl_pct: float = None, sensor_pct: float = None\):)"

    biodiesel_method = r'''    def _get_biodiesel_correction(self, blend_pct: float) -> float:
        """
        🆕 v6.1.0: Calculate correction factor for biodiesel blends.

        Biodiesel has higher dielectric constant → capacitive sensors read high
        Args:
            blend_pct: Biodiesel percentage (0, 5, 10, 20)
        Returns:
            Correction factor (multiply sensor reading)
        """
        if blend_pct <= 0:
            return 1.0
        elif blend_pct <= 5:
            return 0.997  # -0.3%
        elif blend_pct <= 10:
            return 0.994  # -0.6%
        elif blend_pct <= 20:
            return 0.988  # -1.2%
        else:
            return 0.980  # >20% blend

    \1'''

    content = re.sub(init_method_pattern, biodiesel_method, content)
    changes_made.append("✅ Agregado método _get_biodiesel_correction")
else:
    print("⏭️  Método _get_biodiesel_correction ya existe")

# ═══════════════════════════════════════════════════════════════════════════════
# CAMBIO 4: Agregar método _adaptive_measurement_noise_v2 antes de update
# ═══════════════════════════════════════════════════════════════════════════════

if "_adaptive_measurement_noise_v2" not in content:
    # Buscar el método update
    update_pattern = r"(    def update\(self, measured_pct: float\):)"

    adaptive_r_method = r'''    def _adaptive_measurement_noise_v2(self, innovation: float) -> float:
        """
        🆕 v6.1.0: Adaptive R based on consistency (PRODUCTION FEEDBACK).

        Key insight: Persistent bias (all innovations same sign) is different
        from random noise (innovations alternate sign).

        Args:
            innovation: Current residual in %

        Returns:
            Adjusted measurement noise R
        """
        base_R = self.Q_L
        abs_innovation = abs(innovation)

        # Check for persistent bias (all same sign)
        if len(self.innovation_history) >= 4:
            recent = list(self.innovation_history)[-4:]

            # All positive bias?
            if all(i > 1.0 for i in recent):
                self.bias_detected = True
                self.bias_magnitude = sum(recent) / len(recent)
                logger.warning(
                    f"[{self.truck_id}] 🔴 Sensor persistent POSITIVE bias detected: "
                    f"{self.bias_magnitude:.2f}% (last 4: {[f'{i:.1f}' for i in recent]})"
                )
                return base_R * 2.5  # Trust sensor much less

            # All negative bias?
            elif all(i < -1.0 for i in recent):
                self.bias_detected = True
                self.bias_magnitude = sum(recent) / len(recent)
                logger.warning(
                    f"[{self.truck_id}] 🔴 Sensor persistent NEGATIVE bias detected: "
                    f"{self.bias_magnitude:.2f}% (last 4: {[f'{i:.1f}' for i in recent]})"
                )
                return base_R * 2.5  # Trust sensor much less

            # Alternating (healthy random noise)
            else:
                self.bias_detected = False
                self.bias_magnitude = 0.0

        # Standard adaptive R (only if no bias detected)
        if abs_innovation < 2.0:
            return base_R * 0.7  # Small innovation, trust sensor
        elif abs_innovation < 5.0:
            return base_R  # Normal
        elif abs_innovation < 10.0:
            return base_R * 1.5  # Large innovation, suspicious
        else:
            return base_R * 2.5  # Very large, likely glitch

    \1'''

    content = re.sub(update_pattern, adaptive_r_method, content)
    changes_made.append("✅ Agregado método _adaptive_measurement_noise_v2")
else:
    print("⏭️  Método _adaptive_measurement_noise_v2 ya existe")

# ═══════════════════════════════════════════════════════════════════════════════
# CAMBIO 5: Modificar update() para usar biodiesel correction y track innovations
# ═══════════════════════════════════════════════════════════════════════════════

# Buscar y reemplazar el inicio del método update
update_old_pattern = r'''(def update\(self, measured_pct: float\):
        """Update state with measurement using adaptive Kalman gain"""
        # Fix M1: Handle NaN/Inf values to prevent corrupted calculations
        if measured_pct is None or not isinstance\(measured_pct, \(int, float\)\):
            logger\.warning\(f"\[{self\.truck_id}\] Invalid measured_pct: {measured_pct}"\)
            return

        import math

        if math\.isnan\(measured_pct\) or math\.isinf\(measured_pct\):
            logger\.warning\(f"\[{self\.truck_id}\] NaN/Inf measured_pct: {measured_pct}"\)
            return

        # Clamp to valid range
        measured_pct = max\(0\.0, min\(100\.0, measured_pct\)\)

        measured_liters = \(measured_pct / 100\.0\) \* self\.capacity_liters)'''

update_new = r"""\1

        # 🆕 v6.1.0: Apply biodiesel correction
        corrected_pct = measured_pct * self.biodiesel_correction
        corrected_pct = max(0.0, min(100.0, corrected_pct))
        
        measured_liters = (corrected_pct / 100.0) * self.capacity_liters"""

if "corrected_pct = measured_pct * self.biodiesel_correction" not in content:
    content = re.sub(update_old_pattern, update_new, content, flags=re.DOTALL)
    changes_made.append("✅ Actualizado update() para usar biodiesel correction")
else:
    print("⏭️  update() ya usa biodiesel correction")

# ═══════════════════════════════════════════════════════════════════════════════
# CAMBIO 6: Actualizar get_estimate() para incluir bias info
# ═══════════════════════════════════════════════════════════════════════════════

if '"bias_detected"' not in content:
    estimate_pattern = (
        r'(# 🆕 v5\.8\.3: Kalman confidence\s+\n\s+"kalman_confidence": confidence,)'
    )

    estimate_add = r"""\1
            # 🆕 v6.1.0: Sensor bias detection info
            "bias_detected": self.bias_detected,
            "bias_magnitude_pct": round(self.bias_magnitude, 2) if self.bias_detected else 0.0,
            "biodiesel_correction_applied": self.biodiesel_blend_pct > 0,"""

    content = re.sub(estimate_pattern, estimate_add, content)
    changes_made.append("✅ Actualizado get_estimate() para incluir bias info")
else:
    print("⏭️  get_estimate() ya incluye bias info")

# ═══════════════════════════════════════════════════════════════════════════════
# Guardar cambios
# ═══════════════════════════════════════════════════════════════════════════════

if changes_made:
    backup_file = ESTIMATOR_FILE.with_suffix(".py.bak")
    print(f"\n💾 Creando backup en {backup_file}...")
    with open(backup_file, "w", encoding="utf-8") as f:
        # Leer original nuevamente para el backup
        with open(ESTIMATOR_FILE, "r", encoding="utf-8") as original:
            f.write(original.read())

    print(f"📝 Escribiendo cambios en {ESTIMATOR_FILE}...")
    with open(ESTIMATOR_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("\n" + "=" * 80)
    print("✅ CAMBIOS APLICADOS:")
    for change in changes_made:
        print(f"   {change}")
    print("=" * 80)
    print(f"\n🎉 estimator.py actualizado a v6.1.0!")
    print(f"💾 Backup guardado en: {backup_file}")
else:
    print("\n⏭️  Todos los cambios ya estaban aplicados")

print(f"\n📋 PRÓXIMOS PASOS:")
print(f"   1. Ejecutar: python test_kalman_quick.py --truck CO0681")
print(f"   2. Verificar que todos los tests pasen")
print(f"   3. Si hay problemas, restaurar desde backup:")
print(f"      cp {backup_file} {ESTIMATOR_FILE}")
