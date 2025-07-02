# Swiss Public Transport Subscription Optimizer

A Python tool that analyzes your travel patterns and recommends the most cost-effective combination of Swiss public transport subscriptions (GA, Halbtax, ZVV passes, etc.).

## Features

- **Multi-subscription optimization**: Finds the best combination of subscriptions including GA, Halbtax, ZVV zone passes, and time-restricted passes
- **Age-based pricing**: Calculates costs for different age groups (24, 25, 26+)
- **Time-aware coverage**: Handles time-restricted passes like Night-GA (19:00-05:00) and 9-Uhr passes
- **Zone coverage analysis**: Supports Swiss transport zones, canton-wide coverage, and extension ticket calculations
- **Flexible journey modeling**: Define your travel patterns with zones, times, frequencies, and full prices

## How It Works

The optimizer evaluates all possible combinations of subscriptions and calculates:
1. **Subscription costs**: Annual fees for your selected passes
2. **Extension ticket costs**: Additional costs for uncovered zones
3. **Credit benefits**: Travel credits included with Halbtax Plus subscriptions
4. **Total annual cost**: Complete picture of your transport expenses

## Usage

1. **Define your travel patterns** in the `journeys` list:
```python
journeys = [
    {'name': 'work_commute', 'zones': [110, 141], 'time': '08:00', 'full_price': 7.00, 'count': 250},
    {'name': 'family_visits', 'zones': [110, 140, 141, 142], 'time': '12:00', 'full_price': 11.20, 'count': 50},
    # Add more journey patterns...
]
```

2. **Run the optimizer**:
```bash
python ov_berechnung.py
```

3. **Review recommendations** for each age group with top 5 most cost-effective plans.

## Journey Parameters

- `name`: Descriptive name for the journey type
- `zones`: List of zone numbers, 'ZURICH' for canton-wide, or 'all' for Switzerland-wide
- `time`: Departure time in 'HH:MM' format
- `full_price`: Full ticket price without any discounts
- `count`: Annual frequency of this journey type

## Supported Subscriptions

### Core Subscriptions
- **GA (Generalabonnement)**: Unlimited travel throughout Switzerland
- **Halbtax**: 50% discount on all tickets
- **Night-GA**: Free travel 19:00-05:00 throughout Switzerland

### ZVV (Zurich Transport Network)
- Single zone passes (e.g., ZVV_110)
- Multi-zone combinations (e.g., ZVV_110_140_141_142)
- Canton-wide Zurich pass (ZVV_ZURICH)
- Time-restricted 9-Uhr passes

### Halbtax Plus
- Level 1: Halbtax + CHF 1000 travel credit
- Level 2: Halbtax + CHF 2000 travel credit  
- Level 3: Halbtax + CHF 3000 travel credit

## Example Output

```
Age 24 - Top 5 plans:
  1. ['night_GA', 'halbtax', 'ZVV_110_140_141_142']
     Subscription costs: CHF 1593.00 - Single Tickets: CHF 234.50 → total CHF 1827.50
  2. ['night_GA', 'halbtax', 'ZVV_ZURICH']
     Subscription costs: CHF 1863.00 - Single Tickets: CHF 0.00 → total CHF 1863.00
  ...
```

## Extension Ticket Logic

When your subscriptions don't fully cover a journey, the optimizer automatically calculates extension ticket costs:
- **1-2 zones**: CHF 4.60 (CHF 6.40 with Halbtax due to pricing structure)
- **3 zones**: CHF 7.00
- **4+ zones**: CHF 9.20

## Customization

### Fixed Subscriptions
Force certain subscriptions to always be included:
```python
fixed_subscriptions = ['night_GA', 'halbtax']
```

### Age Groups
Modify the age ranges in the main loop:
```python
for age in [24, 25, 26]:  # Customize age groups
```

### Add New Subscriptions
Extend the `subscription_options` list with new passes:
```python
{
    'name': 'new_pass',
    'price': {24: 500, 25: 600, 26: 600},
    'coverage': {'type': 'unlimited', 'zones': [110, 120], 'times': ('00:00', '23:59')}
}
```

## Requirements

- Python 3.6+
- pandas
- No additional dependencies required

## Installation

```bash
git clone https://github.com/yourusername/public_transport_optimizer.git
cd public_transport_optimizer
pip install pandas
python ov_berechnung.py
```

## Contributing

Feel free to contribute by:
- Adding support for other Swiss transport regions
- Implementing additional subscription types
- Improving the optimization algorithm
- Adding data visualization features

## License

This project is licensed under the terms specified in the LICENSE file.

## Disclaimer

This tool is for informational purposes only. Always verify current prices and terms with official transport providers. Prices and subscription details may change.
