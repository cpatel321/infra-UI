"""
Add sample waste depots/transfer stations for Kanpur
"""

from osm_app.models import Depot

# Sample depot locations in Kanpur
depots = [
    {
        'name': 'Kanpur Central Depot',
        'address': 'Near Civil Lines, Kanpur',
        'lat': 26.4650,
        'lon': 80.3500,
        'capacity_kg': 50000,
        'active': True
    },
    {
        'name': 'Kanpur East Transfer Station',
        'address': 'Govind Nagar Area, Kanpur',
        'lat': 26.4800,
        'lon': 80.3800,
        'capacity_kg': 30000,
        'active': True
    },
    {
        'name': 'Kanpur West Depot',
        'address': 'Kalyanpur Area, Kanpur',
        'lat': 26.4900,
        'lon': 80.2800,
        'capacity_kg': 40000,
        'active': True
    },
    {
        'name': 'Kanpur South Station',
        'address': 'Barra Area, Kanpur',
        'lat': 26.4300,
        'lon': 80.3400,
        'capacity_kg': 25000,
        'active': True
    }
]

print("Adding sample depots for Kanpur...")
print("-" * 50)

for depot_data in depots:
    depot, created = Depot.objects.get_or_create(
        name=depot_data['name'],
        defaults=depot_data
    )
    
    if created:
        print(f"Created: {depot.name}")
        print(f"   Location: ({depot.lat:.4f}, {depot.lon:.4f})")
        print(f"   Capacity: {depot.capacity_kg:,} kg/day")
    else:
        print(f"Already exists: {depot.name}")

print("\n" + "=" * 50)
print(f"Total depots in database: {Depot.objects.count()}")
print("=" * 50)
print("\nTip: Wards will be automatically assigned to nearest depot")
print("   when you create a ward configuration.")
