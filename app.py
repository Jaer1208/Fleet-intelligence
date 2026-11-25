"""Streamlit entry point for Fleet Intelligence."""

import plotly.express as px
import streamlit as st

from fleet import (
    SNAPSHOT,
    STATUS_ORDER,
    delivery_summary,
    filter_shipments,
    fuel_by_vehicle,
    generate_data,
    recommendations,
    shipment_csv,
)

COLORS = {
    "Delivered": "#007F73",
    "In transit": "#346BB0",
    "Scheduled": "#71839B",
    "On time": "#007F73",
    "Late": "#C16430",
    "Cargo van": "#007F73",
    "Box truck": "#346BB0",
    "Tractor trailer": "#8052A3",
}


def chart(fig, **layout):
    fig.update_layout(
        height=330, margin=dict(l=8, r=12, t=20, b=8),
        legend=dict(orientation="h", y=1.08), **layout,
    )
    st.plotly_chart(fig, width="stretch")


def tracking_view(shipments):
    left, right = st.columns(2)
    with left:
        st.subheader("Shipment status")
        counts = shipments.status.value_counts().reindex(STATUS_ORDER, fill_value=0)
        chart(px.bar(
            counts.rename("Shipments").rename_axis("Status").reset_index(),
            x="Status", y="Shipments", color="Status", color_discrete_map=COLORS,
        ), showlegend=False)
    with right:
        st.subheader("Delivery performance by lane")
        deliveries = shipments.loc[shipments.status.eq("Delivered")]
        if deliveries.empty:
            st.info("No completed deliveries in this selection.")
        else:
            counts = deliveries.groupby(["lane", "delivery_outcome"]).size().reset_index(name="Deliveries")
            chart(px.bar(
                counts, x="Deliveries", y="lane", color="delivery_outcome",
                color_discrete_map=COLORS, labels={"lane": "", "delivery_outcome": "Outcome"},
                category_orders={"delivery_outcome": ["On time", "Late"]},
            ))

    st.subheader("Shipment register")
    shipment_id = st.selectbox(
        "Inspect a shipment", sorted(shipments.shipment_id), index=None,
        placeholder="Choose a shipment ID",
    )
    if shipment_id:
        shipment = shipments.loc[shipments.shipment_id.eq(shipment_id)].iloc[0]
        arrival = shipment.delivery_date
        actual = "Pending" if shipment.status != "Delivered" else f"{arrival:%b %d, %Y}"
        st.info(f"**{shipment_id} · {shipment.lane} · {shipment.status}**  \n"
                f"Dispatch {shipment.dispatch_date:%b %d, %Y} · "
                f"Due {shipment.due_date:%b %d, %Y} · Delivered {actual}  \n"
                f"{shipment.vehicle_id} · {shipment.driver_name} · {shipment.delivery_outcome}")
    columns = {
        "shipment_id": "Shipment", "lane": "Lane", "status": "Status", "delivery_outcome": "Outcome",
        "dispatch_date": "Dispatch", "due_date": "Due", "delivery_date": "Delivered",
        "vehicle_id": "Vehicle", "driver_name": "Driver",
    }
    register = shipments.sort_values("dispatch_date", ascending=False)[list(columns)].rename(columns=columns)
    st.dataframe(register, hide_index=True, column_config={
        label: st.column_config.DateColumn(format="MMM D, YYYY")
        for label in ("Dispatch", "Due", "Delivered")
    })


def fuel_view(shipments):
    fuel = fuel_by_vehicle(shipments)
    if fuel.empty:
        st.info("No recorded mileage in this selection.")
        return

    total_km = fuel.distance_km.sum()
    total_liters = fuel.fuel_liters.sum()
    left, middle, right = st.columns(3)
    left.metric("Recorded distance", f"{total_km:,} km")
    middle.metric("Fuel used", f"{total_liters:,.1f} L")
    right.metric("Fleet consumption", f"{100 * total_liters / total_km:.1f} L/100 km")
    st.caption("Lower consumption is better. Bars show actuals and diamonds show vehicle-type targets.")

    left, right = st.columns(2)
    with left:
        st.subheader("Consumption by vehicle")
        fig = px.bar(
            fuel, x="vehicle_id", y="l_per_100km", color="vehicle_type",
            color_discrete_map=COLORS, labels={
                "vehicle_id": "Vehicle", "l_per_100km": "L/100 km", "vehicle_type": "Type",
            },
        )
        fig.add_scatter(
            x=fuel.vehicle_id, y=fuel.target_l_per_100km, mode="markers",
            marker=dict(color="#14283F", symbol="diamond", size=8), name="Target",
            hovertemplate="%{x}<br>%{y} L/100 km<extra>Target</extra>",
        )
        chart(fig)
    with right:
        st.subheader("Weekly fuel spend")
        week_ending = shipments.dispatch_date.dt.to_period("W-SUN").dt.end_time.dt.normalize()
        weekly = (
            shipments.groupby(week_ending).fuel_cost_usd.sum()
            .rename("Fuel cost (USD)").reset_index()
        )
        chart(px.line(
            weekly, x="dispatch_date", y="Fuel cost (USD)", markers=True,
            color_discrete_sequence=[COLORS["Delivered"]], labels={"dispatch_date": "Week ending"},
        ))
    st.dataframe(fuel, hide_index=True, column_config={
        "vehicle_id": "Vehicle", "vehicle_type": "Type", "distance_km": "Distance (km)",
        "fuel_liters": st.column_config.NumberColumn("Fuel (L)", format="%.2f"),
        "fuel_cost_usd": st.column_config.NumberColumn("Fuel cost (USD)", format="dollar"),
        "l_per_100km": st.column_config.NumberColumn("Actual (L/100 km)", format="%.1f"),
        "target_l_per_100km": "Target (L/100 km)",
    })


def main():
    st.set_page_config(page_title="Fleet Intelligence", page_icon="🚚", layout="wide")
    vehicles, drivers, shipments = st.cache_data(generate_data)()
    st.title("Fleet Intelligence")
    st.markdown("Shipment tracking, delivery reliability, and fuel performance")
    st.caption(f"Synthetic data · AI-assisted development · Demo snapshot as of {SNAPSHOT:%B %d, %Y}")

    with st.sidebar:
        st.header("Filters")
        first = shipments.dispatch_date.min().date()
        last = shipments.dispatch_date.max().date()
        dates = st.date_input("Dispatch date range", (first, last), min_value=first, max_value=last)
        statuses = st.multiselect("Shipment status", STATUS_ORDER)
        vehicle_ids = st.multiselect("Vehicle", vehicles.vehicle_id)
        driver_ids = st.multiselect(
            "Driver", drivers.driver_id,
            format_func=drivers.set_index("driver_id").driver_name.to_dict().__getitem__,
        )
        st.caption("Leave a filter blank to include all values.")

    if len(dates) != 2:
        st.info("Select both dispatch dates to apply the range.")
        return

    selected = filter_shipments(shipments, *dates, statuses, vehicle_ids, driver_ids)
    left, right = st.columns([3, 1], vertical_alignment="center")
    left.caption(f"Showing {len(selected)} of {len(shipments)} shipments · {len(vehicles)} vehicles · {len(drivers)} drivers")
    right.download_button(
        "Download filtered CSV", shipment_csv(selected), file_name="fleet_shipments.csv",
        mime="text/csv", disabled=selected.empty,
    )

    summary = delivery_summary(selected)
    rate = summary["on_time_rate"]
    metrics = st.columns(4)
    metrics[0].metric("Delivered", summary["delivered"], border=True)
    metrics[1].metric("On-time delivery", "—" if rate is None else f"{rate:.1%}", border=True)
    metrics[2].metric("Overdue shipments", summary["overdue"], border=True)
    metrics[3].metric("Fuel spend", f"${selected.fuel_cost_usd.sum():,.2f}", border=True)

    if selected.empty:
        st.info("No shipments match these filters. Expand the date range or clear a selection.")
        return

    tracking, fuel, assistant = st.tabs(["Shipment tracking", "Fuel analysis", "Operations assistant"])
    with tracking:
        tracking_view(selected)
    with fuel:
        fuel_view(selected)
    with assistant:
        st.subheader("Recommended actions")
        st.caption("Rules use the current filters. Lane alerts require three deliveries and an on-time rate below 85%. "
                   "Vehicle alerts require 300 km and consumption more than 10% above target.")
        actions = recommendations(selected)
        if not actions:
            st.success("No rules were triggered for this selection.")
        for title, detail in actions:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.write(detail)


if __name__ == "__main__":
    main()
