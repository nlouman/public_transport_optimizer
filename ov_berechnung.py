import pandas as pd
import itertools
from datetime import datetime, time

# -----------------------------------------------------------------------------
# Extension‑ticket prices (CHF) for uncovered zones (24 h validity)
EXT_PRICES = {
    "1-2": 4.60,            # 1‑2 uncovered zones
    "1-2 (halbtax)": 6.40,  # special ext. when Halbtax owned
    "3":   7.00,            # 3 uncovered zones
    "4+":  9.20             # 4 or more uncovered zones
}

# -----------------------------------------------------------------------------
# Helper functions

def _parse_time(t):
    return t if isinstance(t, time) else datetime.strptime(t, "%H:%M").time()


def _in_range(t, start, end):
    t, start, end = map(_parse_time, (t, start, end))
    return (start <= end and start <= t <= end) or (start > end and (t >= start or t <= end))


# Zone‑coverage utility --------------------------------------------------------


def _covers(zone_cov, zone_req):
    """Return True if *zone_cov* covers *zone_req* (strings or lists).
    Handles zone_cov/zone_req as str or list; recognizes 'ZURICH' and 'all'."""
    # normalise cov
    cov_list = zone_cov if isinstance(zone_cov, list) else [zone_cov]
    req_list = zone_req if isinstance(zone_req, list) else [zone_req]

    # Full‑country GA‑style coverage
    if "all" in cov_list:
        return True

    # Request is Switzerland‑wide; only GA covers it
    if zone_req == "all":
        return False

    # Canton coverage covers any numeric zones and 'ZURICH' itself
    if "ZURICH" in cov_list:
        # covers canton request or any numeric zone list
        if zone_req == "ZURICH":
            return True
        if isinstance(zone_req, list):
            return True

    # Otherwise compare numeric zone sets (lists)
    if isinstance(zone_cov, list) and isinstance(zone_req, list):
        return set(req_list).issubset(set(cov_list))
    
    if zone_req == "ZURICH":
        return zone_cov in ("all", "ZURICH")
    if zone_cov == "ZURICH" and isinstance(zone_req, list):
        return True  # canton covers any numeric zones
    # both lists of numerics?
    if isinstance(zone_cov, list) and isinstance(zone_req, list):
        return set(zone_req).issubset(zone_cov)
    return False


def _is_redundant(combo):
    """True if any unlimited pass in *combo* is subsumed by another."""
    unlimited = [s for s in combo if s.get("coverage", {}).get("type") == "unlimited"]
    for a, b in itertools.permutations(unlimited, 2):
        # if zones of a covered by b and time window of b is super/equal a
        cov_a, cov_b = a["coverage"], b["coverage"]
        if _covers(cov_b["zones"], cov_a["zones"]):
            # time check – if b starts earlier or same and ends later or same
            start_a, end_a = map(_parse_time, cov_a.get("times", ("00:00","23:59")))
            start_b, end_b = map(_parse_time, cov_b.get("times", ("00:00","23:59")))
            # Convert both intervals to sets of minute indices for robust wrap check is overkill; assume 00‑23 full‑day -> superset.
            if (start_b == _parse_time("00:00") and end_b == _parse_time("23:59")) or (start_b <= start_a and (end_b >= end_a or start_b > end_b)):
                return True
    return False

# -----------------------------------------------------------------------------
# Discount helper

def _apply_discount(j, subs):
    rates = [s["coverage"]["rate"] for s in subs if s.get("coverage", {}).get("type") == "discount"]
    return j["full_price"] * min(rates, default=1.0)

# -----------------------------------------------------------------------------
# Per‑journey pricing

def _journey_price(j, subs):
    zones, dep = j["zones"], j["time"]

    # 1️⃣ Unlimited coverage valid at departure
    has_global, canton, numer = False, False, set()
    for s in subs:
        cov = s.get("coverage", {})
        if cov.get("type") != "unlimited" or not _in_range(dep, *cov.get("times", ("00:00","23:59"))):
            continue
        zc = cov["zones"] if isinstance(cov["zones"], list) else [cov["zones"]]
        if "all" in zc:
            has_global = True; break
        if "ZURICH" in zc:
            canton = True
        numer.update(z for z in zc if isinstance(z, int))

    if has_global:
        return 0.0

    # 2️⃣ Evaluate coverage
    if zones == "ZURICH":
        return 0.0 if canton else _apply_discount(j, subs)

    if isinstance(zones, list):
        if canton or numer.issuperset(zones):
            return 0.0
        if canton or numer:
            missing = [z for z in zones if z not in numer and not canton]
            cnt = sum(2 if z == 110 else 1 for z in missing)
            if cnt <= 2:
                key = "1-2 (halbtax)" if any(s["name"] == "halbtax" for s in subs) else "1-2"
                return EXT_PRICES[key]
            return EXT_PRICES["3" if cnt == 3 else "4+"]

    return _apply_discount(j, subs)

# -----------------------------------------------------------------------------
# Optimisation

def top_k_plans(journeys, options, age, k=3, fixed_sub_names=None):
    fixed = set(fixed_sub_names or [])
    fixed_passes = [s for s in options if s["name"] in fixed]
    variable = [s for s in options if s["name"] not in fixed and s["name"] != "no_sub"]

    plans = []
    for r in range(len(variable)+1):
        for extra in itertools.combinations(variable, r):
            combo = fixed_passes + list(extra)
            names = {s["name"] for s in combo}

            # Skip redundant combos (dominated passes)
            if _is_redundant(combo):
                continue

            # Age & dependency checks
            if any(age not in s["price"] for s in combo):
                continue
            if any(n.startswith("halbtax_plus") for n in names) and "halbtax" not in names:
                continue

            fee = sum(s["price"][age] for s in combo)
            trips = sum(_journey_price(j, combo) * j["count"] for j in journeys)
            credit = sum(s.get("credit", {}).get(age, 0) for s in combo)
            net = max(0.0, trips - credit)
            total = fee + net

            plans.append({
                "subs": combo,
                "subscription_cost": fee,
                "other_cost": net,
                "cost": total
            })

    # Baseline no‑sub option when no fixed passes
    if not fixed and not any(len(p["subs"]) == 0 for p in plans):
        base = sum(j["full_price"]*j["count"] for j in journeys)
        plans.append({"subs": (),"subscription_cost":0.0,"other_cost":base,"cost":base})

    return sorted(plans, key=lambda x: x["cost"])[:k]

if __name__ == '__main__':
    # Define your yearly travel patterns here
    journeys = [
        ################################################################################################
        { 'name': 'default',        'zones': [110], 'time': '12:00', 'full_price': 4.60, 'count': 584 },
        { 'name': 'default_early',  'zones': [110], 'time': '08:00', 'full_price': 4.60, 'count': 292 },
        { 'name': 'default_late',   'zones': [110], 'time': '20:00', 'full_price': 4.60, 'count': 584 },
        ################################################################################################
        { 'name': 'family',         'zones': [110, 140, 141, 142], 'time': '12:00', 'full_price': 11.20, 'count': 50 },
        { 'name': 'family_early',   'zones': [110, 140, 141, 142], 'time': '08:00', 'full_price': 11.20, 'count': 10 },
        { 'name': 'family_late',    'zones': [110, 140, 141, 142], 'time': '20:00', 'full_price': 11.20, 'count': 44 },
        ################################################################################################
        { 'name': 'airport_etc',    'zones': [110, 121], 'time': '12:00', 'full_price': 7.00, 'count': 4 },
        { 'name': 'airport_etc',    'zones': [110, 121], 'time': '08:00', 'full_price': 7.00, 'count': 10 },
        { 'name': 'airport_etc',    'zones': [110, 121], 'time': '20:00', 'full_price': 7.00, 'count': 10 },
        ################################################################################################
        { 'name': 'work',           'zones': [110, 141], 'time': '12:00', 'full_price': 7.00, 'count': 50},
        { 'name': 'work_early',     'zones': [110, 141], 'time': '08:00', 'full_price': 7.00, 'count': 42 },
        { 'name': 'work_late',      'zones': [110, 141], 'time': '20:00', 'full_price':  7.00, 'count': 12 },
        ################################################################################################
        { 'name': 'canton',         'zones': 'ZURICH', 'time': '12:00', 'full_price':  17.80, 'count': 10 },
        { 'name': 'canton_early',   'zones': 'ZURICH', 'time': '08:00', 'full_price':  17.80, 'count': 6 },
        { 'name': 'canton_late',    'zones': 'ZURICH', 'time': '20:00', 'full_price':  17.80, 'count': 6 },
        ################################################################################################
        { 'name': 'suisse',         'zones': 'all', 'time': '12:00', 'full_price': 35.00, 'count':  12 },
        { 'name': 'suisse_early',   'zones': 'all', 'time': '08:00', 'full_price': 35.00, 'count':  4 },
        { 'name': 'suisse_late',    'zones': 'all', 'time': '20:00', 'full_price': 35.00, 'count':  8 },
        ################################################################################################
        { 'name': 'holiday',          'zones': 'all', 'time': '12:00', 'full_price': 4.60, 'count': 30 },
        { 'name': 'holiday_early',    'zones': 'all', 'time': '08:00', 'full_price': 4.60, 'count': 10 },
        { 'name': 'holiday_late',     'zones': 'all', 'time': '20:00', 'full_price': 4.60, 'count': 30 },
        ################################################################################################
    ]

    # Define subscription options, now differentiated by zone sets
    subscription_options = [
        {
            'name': 'no_sub', 
            'price': {24:0,25:0,26:0}, 
            'coverage': {'type':'none'}
        },
        {
            'name': 'halbtax', 
            'price': {24:100,25:190,26:170}, 
            'coverage': {'type':'discount','rate':0.5}
        },
        {
            'name': 'halbtax_plus_level1',
            'price': {24:600, 25:800, 26:800},
            'coverage': {'type':'discount','rate':0.5},
            'credit':   {24:1000, 25:1000, 26:1000}
        },
        {
            'name': 'halbtax_plus_level2',
            'price': {24:1125, 25:1500, 26:1500},
            'coverage': {'type':'discount','rate':0.5},
            'credit':   {24:2000, 25:2000, 26:2000}
        },
        {
            'name': 'halbtax_plus_level3',
            'price': {24:1575, 25:2100, 26:2100},
            'coverage': {'type':'discount','rate':0.5},
            'credit':   {24:3000, 25:3000, 26:3000}
        },
        {
            'name':     'night_GA',      # Night-GA: free travel 19:00-05:00
            'price':    {24: 100},
            'coverage': {'type': 'unlimited', 'zones': 'all', 'times': ('19:00', '05:00')}
        },
        {
            'name':     'GA',      # Generalabonnement for all Switzerland
            'price':    {24: 2780, 25: 3495, 26: 3995},
            'coverage': {'type': 'unlimited', 'zones': 'all', 'times': ('00:00', '23:59')}
        },
        {
            'name':     'ZVV_110',
            'price':    {24: 586,  25: 809,  26: 809},
            'coverage': {'type': 'unlimited', 'zones': [110], 'times': ('00:00', '23:59')}
        },
        {
            'name':     'ZVV_110_140', # Work
            'price':    {24: 861,  25:1189,  26:1189},
            'coverage': {'type': 'unlimited', 'zones': [110, 140], 'times': ('00:00', '23:59')}
        },
        {
            'name':     'ZVV_9_Uhr_110_111_121_140_150_154_155',
            'price':    {24: 827,  25:  827,  26:   827},
            'coverage': {'type': 'unlimited', 'zones': [110, 111, 121, 140, 150, 154, 155], 'times': ('09:00', '05:00')}
        },
        {
            'name':     'ZVV_9_Uhr_ZURICH',
            'price':    {24: 1282,  25:  1282,  26:   1282},
            'coverage': {'type': 'unlimited', 'zones': ['ZURICH'], 'times': ('09:00', '05:00')}
        },
        {
            'name':     'ZVV_110_140_141_142',  # Family
            'price':    {24:1393, 25:1922,  26:1922.},
            'coverage': {'type': 'unlimited', 'zones': [110, 140, 141, 142], 'times': ('00:00', '23:59')}
        },
        {
            'name':     'ZVV_ZURICH',  # Canton of Zurich
            'price':    {24:1663, 25:2295,  26:2295},
            'coverage': {'type': 'unlimited', 'zones': ['ZURICH'], 'times': ('00:00', '23:59')}
        }
    ]

    # Extension ticket prices (CHF) for single journeys. 24h (return) is double price.
    extension_ticket_prices = {
        '1-2 (halbtax)': 6.40, # gets halfed later which is the correct price. needs to be different from '1-2' since it's not half the price with halbtax
        '1-2': 4.60,   # price for 1-2 zone extension
        '3':   7.00,   # price for 3-zone extension
        '4+': 9.20    # price for 4 or more zones
    }

    fixed_subscriptions = ['night_GA', 'halbtax']

    for age in [24, 25, 26]:
        print(f"Age {age} - Top 5 plans:")
        for i, plan in enumerate(top_k_plans(journeys, subscription_options, age, k=5, fixed_sub_names=fixed_subscriptions), 1):
            names = [s["name"] for s in plan["subs"]] or ["(no subscriptions)"]
            print(
                f"  {i}. {names}\n     Subscription costs: CHF {plan['subscription_cost']:.2f}"
                f" - Single Tickets: CHF {plan['other_cost']:.2f} → total CHF {plan['cost']:.2f}"
            )