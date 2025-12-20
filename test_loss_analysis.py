from database_mysql import get_enhanced_loss_analysis
import json

result = get_enhanced_loss_analysis(1)
summary = result.get('summary', {})
by_cause = summary.get('by_cause', {})

print("=" * 60)
print("LOSS ANALYSIS - TODAY")
print("=" * 60)

total = by_cause.get('total', {})
print(f"\n💰 TOTAL LOSS: ${total.get('usd', 0):.2f} ({total.get('gal', 0):.1f} gallons)")

print(f"\n📊 BY CAUSE:")
for cause, data in by_cause.items():
    if cause != 'total' and data.get('usd', 0) > 0:
        print(f"  {cause}: ${data['usd']:.2f} ({data['gal']:.1f} gal)")

print(f"\n🚛 TRUCKS ANALYZED: {len(result.get('trucks', []))}")
print("=" * 60)
