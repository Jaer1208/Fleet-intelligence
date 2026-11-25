"""Synthetic fleet data and dashboard calculations."""

from datetime import timedelta
from random import Random

import pandas as pd

SNAPSHOT = pd.Timestamp("2026-06-30")
VEHICLE_TARGETS = {"Cargo van": 12, "Box truck": 21, "Tractor trailer": 32}
STATUS_ORDER = ["Delivered", "In transit", "Scheduled"]
LANES = [
    ("Chicago", "Detroit", 455),
    ("Dallas", "Houston", 385),
    ("Atlanta", "Charlotte", 395),
    ("Denver", "Kansas City", 970),
    ("Phoenix", "San Diego", 570),
    ("Columbus", "Indianapolis", 280),
]


def generate_data(seed=42):
    """Return vehicle, driver and enriched shipment tables for a fixed snapshot."""
    rng = Random(seed)
    vehicle_types = list(VEHICLE_TARGETS)
    vehicles = pd.DataFrame([
        {
            "vehicle_id": f"VH-{i + 1:02}",
            "vehicle_type": vehicle_types[i % 3],
            "target_l_per_100km": VEHICLE_TARGETS[vehicle_types[i % 3]],
        }
        for i in range(15)
    ])
    drivers = pd.DataFrame([
        {"driver_id": f"DR-{i + 1:02}", "driver_name": f"Demo Driver {i + 1:02}"}
        for i in range(15)
    ])

    rows = []
    for i in range(60):
        vehicle = vehicles.iloc[i % len(vehicles)]
        driver = drivers.iloc[(i + i // len(vehicles)) % len(drivers)]
        dispatch = SNAPSHOT - timedelta(days=57 - i)
        origin, destination, planned_km = LANES[(i + i // 6) % len(LANES)]
        due = dispatch + timedelta(days=1 if planned_km < 600 else 2)
        delivered = pd.NaT
        if dispatch > SNAPSHOT:
            status, distance = "Scheduled", 0
        elif i >= 49:
            status = "In transit"
            distance = round(planned_km * rng.uniform(0.2, 0.85)) if dispatch < SNAPSHOT else 0
        else:
            status = "Delivered"
            delivered = due + timedelta(days=rng.choice([-1, 0, 0, 0, 0, 1, 2]))
            distance = round(planned_km * rng.uniform(1.0, 1.12))

        efficiency_factor = 1.28 if i % 15 in (2, 8, 11) else 1.0
        liters = round(distance / 100 * vehicle.target_l_per_100km * efficiency_factor
                       * rng.uniform(0.91, 1.10), 2)
        rows.append({
            "shipment_id": f"SHP-{i + 1:03}",
            "vehicle_id": vehicle.vehicle_id,
            "driver_id": driver.driver_id,
            "origin": origin,
            "destination": destination,
            "dispatch_date": dispatch,
            "due_date": due,
            "delivery_date": delivered,
            "status": status,
            "planned_km": planned_km,
            "distance_km": distance,
            "fuel_liters": liters,
            "fuel_cost_usd": round(liters * rng.uniform(0.95, 1.23), 2),
        })

    shipments = (
        pd.DataFrame(rows)
        .merge(vehicles, on="vehicle_id", validate="many_to_one")
        .merge(drivers, on="driver_id", validate="many_to_one")
    )
    shipments["delivery_outcome"] = "Pending"
    shipments.loc[shipments.delivery_date.notna(), "delivery_outcome"] = "Late"
    shipments.loc[shipments.delivery_date.le(shipments.due_date), "delivery_outcome"] = "On time"
    shipments.loc[
        shipments.status.eq("In transit") & shipments.due_date.lt(SNAPSHOT),
        "delivery_outcome",
    ] = "Overdue"
    shipments["lane"] = shipments.origin + " → " + shipments.destination
    return vehicles, drivers, shipments


def filter_shipments(shipments, start, end, statuses=(), vehicles=(), drivers=()):
    """Match an inclusive dispatch window and any selected dimensions."""
    mask = shipments.dispatch_date.between(pd.Timestamp(start), pd.Timestamp(end))
    for column, values in (
        ("status", statuses), ("vehicle_id", vehicles), ("driver_id", drivers)
    ):
        if values:
            mask &= shipments[column].isin(values)
    return shipments.loc[mask]


def delivery_summary(shipments):
    delivered = shipments.status.eq("Delivered")
    on_time = shipments.delivery_outcome.eq("On time")
    completed = int(delivered.sum())
    return {
        "delivered": completed,
        "on_time_rate": float(on_time.sum() / completed) if completed else None,
        "overdue": int(shipments.delivery_outcome.eq("Overdue").sum()),
    }


def fuel_by_vehicle(shipments):
    """Aggregate recorded mileage and fuel, then calculate weighted consumption."""
    summary = (
        shipments.loc[shipments.distance_km.gt(0)]
        .groupby(["vehicle_id", "vehicle_type", "target_l_per_100km"], as_index=False)
        [["distance_km", "fuel_liters", "fuel_cost_usd"]].sum()
    )
    summary["l_per_100km"] = 100 * summary.fuel_liters / summary.distance_km
    return summary


def recommendations(shipments):
    """Return triggered rules and concrete actions for the filtered shipments."""
    alerts = []
    overdue = shipments.loc[shipments.delivery_outcome.eq("Overdue"), "shipment_id"]
    if not overdue.empty:
        alerts.append((
            "Contact dispatch about overdue shipments",
            f"{len(overdue)} overdue · {', '.join(overdue)}. Confirm current locations, "
            "update ETAs, and notify recipients.",
        ))

    delivered = shipments.loc[shipments.status.eq("Delivered")].copy()
    delivered["on_time"] = delivered.delivery_outcome.eq("On time")
    lanes = delivered.groupby("lane").on_time.agg(["mean", "size"])
    for lane, row in lanes.loc[lanes["size"].ge(3) & lanes["mean"].lt(0.85)].iterrows():
        alerts.append((
            f"Review the {lane} schedule",
            f"{row['mean']:.0%} on time across {row['size']:.0f} deliveries "
            "(target 85%). Check loading and transit buffers.",
        ))

    fuel = fuel_by_vehicle(shipments)
    inefficient = fuel.loc[
        fuel.distance_km.ge(300) & fuel.l_per_100km.gt(fuel.target_l_per_100km * 1.10)
    ]
    for vehicle in inefficient.itertuples():
        alerts.append((
            f"Investigate fuel consumption for {vehicle.vehicle_id}",
            f"{vehicle.l_per_100km:.1f} L/100 km over {vehicle.distance_km:,} km "
            f"against a {vehicle.target_l_per_100km} L/100 km target. "
            "Review idling, tire pressure, and vehicle load.",
        ))
    return alerts


def shipment_csv(shipments):
    return shipments.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8")
