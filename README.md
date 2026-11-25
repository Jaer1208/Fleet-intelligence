# Fleet Intelligence

Fleet Intelligence is a logistics portfolio dashboard built with Python, Streamlit, Pandas, and Plotly. It brings shipment tracking, delivery performance, and fuel analysis into one view, with a rule-based assistant that flags issues for dispatch and fleet operators.

**Data and development disclosure.** The project uses a reproducible synthetic dataset of 15 vehicles, 15 fictional drivers, and 60 shipments. City names provide geographic context for simulated routes. The repository and app contain no confidential company information, real driver records, or live telemetry. Development was AI-assisted. The operations assistant runs deterministic rules locally and requires no AI service or API key.

## Included datasets

The `data/` directory contains CSV snapshots of the 15 vehicles, 15 drivers, and 60 shipments for use outside the dashboard. The app generates the same data on startup using the default seed in `fleet.py`.

## Quick start

Use Python 3.11 or newer. The automated workflow runs on Python 3.12.

```bash
git clone https://github.com/Jaer1208/Fleet-intelligence.git
cd Fleet-intelligence
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`. Open [localhost:8501](http://localhost:8501) if Streamlit does not open your browser automatically.

## How to use the dashboard

1. Use the sidebar to filter by dispatch dates, shipment status, vehicle, and driver. The date range includes both endpoints. A blank multiselect includes all values for that field. Every tab, KPI, and CSV export uses the same selection.
2. In **Shipment tracking**, compare status counts and completed deliveries by lane. Select a shipment ID to see its dispatch date, due date, actual delivery date, assigned driver, and vehicle.
3. In **Fuel analysis**, compare recorded consumption with vehicle-type targets, explore weekly fuel spend, and review per-vehicle distance, fuel volume, and cost. Plotly charts support hovering, zooming, and legend toggling where applicable.
4. In **Operations assistant**, review actions for overdue shipments, underperforming lanes, and vehicles exceeding fuel targets.
5. Choose **Download filtered CSV** to export matching shipment rows with assignments, dates, outcomes, distance, and fuel metrics.

## Metrics and rules

The dashboard evaluates the fictional fleet as of June 30, 2026. Dispatch dates extend beyond the snapshot for scheduled shipments.

| Metric or rule | Calculation |
| --- | --- |
| On-time delivery | Completed deliveries on or before their due date divided by all completed deliveries. |
| Overdue shipments | In-transit shipments whose due date precedes the snapshot date. |
| Fuel consumption | Total recorded liters divided by total recorded kilometers, multiplied by 100. In-transit shipments can include partial mileage. |
| Weekly fuel spend | Recorded fuel costs in USD grouped by dispatch week, ending Sunday. Cost is attributed to the shipment’s dispatch week. |
| Lane recommendation | At least three completed deliveries and an on-time rate below 85%. |
| Vehicle recommendation | At least 300 recorded kilometers and consumption more than 10% above the vehicle-type target. |

## Project structure and tests

- `app.py` renders the dashboard, interactive charts, and download controls.
- `fleet.py` generates data and implements filtering, metrics, recommendations, and CSV export.
- `tests/` covers data integrity, business logic, CSV output, and dashboard interactions through Streamlit AppTest.
- `.github/workflows/tests.yml` runs the automated suite on pull requests to `main` and pushes to `main`.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
