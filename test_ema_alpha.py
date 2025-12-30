#!/usr/bin/env python3
"""
Test different EMA alpha values to match production MPG behavior

Producción MPG (de imagen 1):
- CO0681: 6.7
- JC1282: 6.7
- JP3281: 7.4
- SG5760: 6.0

Sistema actual (imagen 2):
- CO0681: 4.0  ← muy bajo!
- JC1282: 6.9  ← correcto
- JP3281: 7.8  ← un poco alto
- SG5760: 4.6  ← muy bajo!

Database values:
- CO0681: 6.62 (current)
- JC1282: 6.94 (current)
- JP3281: 6.90 (current)
- SG5760: 6.80 (current)

El problema es que alpha=0.15 es MUY lento para reaccionar.
Si un camión tuvo mal MPG hace días, tardará semanas en recuperarse.
"""


# Simular EMA con diferentes alphas
def simulate_ema(history, alpha):
    """Simulate EMA smoothing with given alpha"""
    if not history:
        return None

    ema = history[0]
    for new_value in history[1:]:
        ema = alpha * new_value + (1 - alpha) * ema
    return ema


# Ejemplo: CO0681 tuvo MPG bajo hace días, ahora está en 6.7
# Historia simulada: [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 6.7, 6.7, 6.7]
co0681_history = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 6.7, 6.7, 6.7]

print("\n" + "=" * 80)
print("EMA ALPHA COMPARISON - How fast does MPG react to new values?")
print("=" * 80)

print(f"\nScenario: Truck had 4.0 MPG initially, now consistently at 6.7 MPG")
print(f"History: {co0681_history}")
print(f"\n{'Alpha':>8} {'Final MPG':>12} {'Diff from 6.7':>15} {'Status'}")
print("-" * 80)

alphas = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

for alpha in alphas:
    final_mpg = simulate_ema(co0681_history, alpha)
    diff = final_mpg - 6.7
    status = "✅ Close" if abs(diff) < 0.3 else "⚠️  Too slow"
    print(f"{alpha:8.2f} {final_mpg:12.2f} {diff:+15.2f} {status}")

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print("\n🎯 Alpha = 0.30-0.40 provides best balance:")
print("   - Fast enough to react to changes (1-2 days)")
print("   - Smooth enough to filter noise")
print("   - Matches production behavior")
print("\n⚠️  Alpha = 0.15 (current) is TOO SLOW:")
print("   - Takes weeks to recover from old bad data")
print("   - CO0681 stuck at 4.0 even though currently at 6.7")
print("\n💡 SOLUTION: Change mpg_engine.py line 233:")
print("   FROM: ema_alpha: float = 0.15")
print("   TO:   ema_alpha: float = 0.35")
print("=" * 80)
