import yaml

# Load tanks.yaml
with open('tanks.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Get all truck IDs
truck_ids = list(data['trucks'].keys())

print("Trucks in tanks.yaml:")
for truck in truck_ids:
    print(truck)

print(f"\nTotal trucks: {len(truck_ids)}")