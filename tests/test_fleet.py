from io import BytesIO

import pandas as pd
import pytest

from fleet import (
    SNAPSHOT,
    delivery_summary,
    filter_shipments,
    fuel_by_vehicle,
    generate_data,
    recommendations,
    shipment_csv,
)


@pytest.fixture
def shipments():
    return generate_data()[2]


def test_synthetic_data_counts_and_integrity(shipments):
    vehicles, drivers, repeated = generate_data()
    assert vehicles.vehicle_id.nunique() == len(vehicles) == 15
    assert drivers.driver_id.nunique() == len(drivers) == 15
    assert shipments.shipment_id.nunique() == len(shipments) == 60
    assert set(shipments.vehicle_id) == set(vehicles.vehicle_id)
    assert set(shipments.driver_id) == set(drivers.driver_id)
    pd.testing.assert_frame_equal(shipments, repeated)
    delivered = shipments.loc[shipments.status.eq("Delivered")]
    assert delivered.delivery_date.between(delivered.dispatch_date, SNAPSHOT).all()
    assert shipments.loc[shipments.status.ne("Delivered"), "delivery_date"].isna().all()
    scheduled = shipments.loc[shipments.status.eq("Scheduled")]
    assert scheduled.dispatch_date.gt(SNAPSHOT).all()
    assert scheduled[["distance_km", "fuel_liters", "fuel_cost_usd"]].eq(0).all().all()


def test_filter_intersects_dimensions_and_includes_range_boundaries(shipments):
    row = shipments.iloc[0]
    match = filter_shipments(
        shipments, row.dispatch_date, row.dispatch_date,
        [row.status], [row.vehicle_id], [row.driver_id],
    )
    assert match.shipment_id.tolist() == [row.shipment_id]
    assert filter_shipments(shipments, row.dispatch_date, row.dispatch_date, ["Scheduled"]).empty


def test_delivery_metrics_use_only_completed_shipments(shipments):
    summary = delivery_summary(shipments)
    delivered = shipments.loc[shipments.status.eq("Delivered")]
    assert summary["delivered"] == len(delivered)
    assert summary["on_time_rate"] == delivered.delivery_date.le(delivered.due_date).mean()
    assert summary["overdue"] == (
        shipments.status.eq("In transit") & shipments.due_date.lt(SNAPSHOT)
    ).sum()
    assert delivery_summary(shipments.iloc[0:0])["on_time_rate"] is None


def test_vehicle_consumption_is_distance_weighted(shipments):
    fuel = fuel_by_vehicle(shipments)
    vehicle = fuel.iloc[0]
    trips = shipments.loc[shipments.vehicle_id.eq(vehicle.vehicle_id)]
    assert vehicle.l_per_100km == pytest.approx(100 * trips.fuel_liters.sum() / trips.distance_km.sum())
    assert fuel.fuel_cost_usd.sum() == pytest.approx(shipments.fuel_cost_usd.sum())
    assert fuel_by_vehicle(shipments.loc[shipments.status.eq("Scheduled")]).empty


def test_assistant_reports_each_rule_and_respects_empty_selection(shipments):
    messages = [title for title, _ in recommendations(shipments)]
    assert any("overdue shipments" in title for title in messages)
    assert any("schedule" in title for title in messages)
    assert any("fuel consumption" in title for title in messages)
    assert recommendations(shipments.iloc[0:0]) == []
    assert recommendations(shipments.loc[shipments.status.eq("Scheduled")]) == []


def test_csv_matches_filtered_rows(shipments):
    filtered = shipments.loc[shipments.status.eq("In transit")]
    exported = pd.read_csv(BytesIO(shipment_csv(filtered)))
    assert exported.columns.tolist() == filtered.columns.tolist()
    assert exported.shipment_id.tolist() == filtered.shipment_id.tolist()
    assert exported.dispatch_date.tolist() == filtered.dispatch_date.dt.strftime("%Y-%m-%d").tolist()
