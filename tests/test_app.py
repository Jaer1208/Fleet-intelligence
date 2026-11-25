from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_loads_and_inspects_shipment():
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert app.title[0].value == "Fleet Intelligence"
    assert len(app.get("plotly_chart")) == 4
    assert app.dataframe[0].value.shape[0] == 60
    assert app.get("download_button")[0].proto.label == "Download filtered CSV"
    app.selectbox[0].select("SHP-001").run()
    assert not app.exception
    assert any("SHP-001" in notice.value for notice in app.info)


def test_filter_updates_dashboard_and_handles_no_results():
    app = AppTest.from_file(str(APP)).run()
    app.sidebar.multiselect[0].set_value(["Scheduled"]).run()
    assert not app.exception
    assert app.metric[0].value == "0"
    assert app.dataframe[0].value.shape[0] == 2
    assert any("No recorded mileage" in notice.value for notice in app.info)
    assert app.success[0].value == "No rules were triggered for this selection."
    app.sidebar.multiselect[1].set_value(["VH-01"]).run()
    assert not app.exception
    assert any("No shipments match" in notice.value for notice in app.info)
    assert app.get("download_button")[0].proto.disabled


def test_incomplete_date_selection_displays_prompt():
    app = AppTest.from_file(str(APP)).run()
    first, _ = app.sidebar.date_input[0].value
    app.sidebar.date_input[0].set_value((first,)).run()
    assert not app.exception
    assert "Select both dispatch dates" in app.info[0].value
