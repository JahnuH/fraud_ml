import ast
import json
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path
from uuid import uuid4

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import folium
from sqlalchemy import text
from streamlit_folium import st_folium

from app.db.postgres import get_sqlalchemy_engine


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_API_BASE = "http://127.0.0.1:8000"
COUNTRY_CODES = ["IN", "US", "UK", "SG", "AE", "CA", "AU", "DE", "FR", "JP"]


st.set_page_config(page_title="Behavioral Anomaly Testing UI", layout="wide")


def _apply_geo_picker_selection() -> None:
    map_state = st.session_state.get("geo_picker_map", {})
    clicked = map_state.get("last_clicked") if isinstance(map_state, dict) else None
    if not clicked:
        return

    lat_value = f"{clicked['lat']:.6f}"
    lon_value = f"{clicked['lng']:.6f}"
    click_signature = (lat_value, lon_value)
    if st.session_state.get("geo_picker_last_click") == click_signature:
        return

    st.session_state["geo_picker_last_click"] = click_signature
    st.session_state["geo_lat_value"] = lat_value
    st.session_state["geo_lon_value"] = lon_value


def _sync_geo_coordinate_widgets() -> None:
    st.session_state["geo_lat"] = st.session_state.get("geo_lat_value", "12.9716")
    st.session_state["geo_lon"] = st.session_state.get("geo_lon_value", "77.5946")


def load_dataframe(query: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_sqlalchemy_engine()
    try:
        return pd.read_sql_query(text(query), engine, params=params)
    finally:
        engine.dispose()


def run_generation_script(
    customers: int,
    months: int,
    inject_time_shift: bool,
    inject_amount_spike: bool,
    inject_new_ip: bool,
) -> dict:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "generate_transactions.py"),
        "--customers",
        str(customers),
        "--months",
        str(months),
        "--inject-time-shift",
        str(inject_time_shift).lower(),
        "--inject-amount-spike",
        str(inject_amount_spike).lower(),
        "--inject-new-ip",
        str(inject_new_ip).lower(),
        "--output",
        "postgres",
        "--summary-json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, cwd=PROJECT_ROOT, check=True)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def run_post_generation_pipeline(run_scoring: bool) -> dict:
    extract_command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "extract_behavioral_features.py"),
    ]
    extract_completed = subprocess.run(extract_command, capture_output=True, text=True, cwd=PROJECT_ROOT, check=True)

    result = {
        "feature_output": extract_completed.stdout.strip(),
        "score_output": "",
    }
    if run_scoring:
        score_command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_behavior_scoring.py"),
        ]
        score_completed = subprocess.run(score_command, capture_output=True, text=True, cwd=PROJECT_ROOT, check=True)
        result["score_output"] = score_completed.stdout.strip()
    return result


def clear_behavior_history() -> None:
    engine = get_sqlalchemy_engine()
    truncate_sql = text(
        """
        TRUNCATE TABLE raw_transactions, behavioral_profiles, scoring_results
        RESTART IDENTITY CASCADE
        """
    )
    try:
        with engine.begin() as connection:
            connection.execute(truncate_sql)
    finally:
        engine.dispose()


def parse_reason_array(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (ValueError, SyntaxError):
            pass
        cleaned = value.strip("{}")
        if not cleaned:
            return []
        return [part.strip().strip('"') for part in cleaned.split(",") if part.strip()]
    return [str(value)]


def load_visualization_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    transactions = load_dataframe(
        """
        SELECT
            rt.event_id,
            rt.event_ts,
            rt.account_id,
            rt.amount,
            rt.country,
            rt.geo_coordinates,
            rt.mcc,
            sr.behavior_score,
            sr.behavior_change,
            sr.behavior_reasons
        FROM raw_transactions rt
        LEFT JOIN scoring_results sr ON rt.event_id = sr.event_id
        ORDER BY rt.event_ts
        """
    )
    profiles = load_dataframe("SELECT * FROM behavioral_profiles ORDER BY account_id")
    scoring = load_dataframe("SELECT * FROM scoring_results")
    return transactions, profiles, scoring


def render_single_transaction_tester() -> None:
    st.subheader("Single Transaction Tester")
    api_base = st.text_input("FastAPI Base URL", value=DEFAULT_API_BASE)

    if "geo_lat_value" not in st.session_state:
        st.session_state["geo_lat_value"] = "12.9716"
    if "geo_lon_value" not in st.session_state:
        st.session_state["geo_lon_value"] = "77.5946"
    if "geo_picker_last_click" not in st.session_state:
        st.session_state["geo_picker_last_click"] = None

    _sync_geo_coordinate_widgets()

    st.caption("Enter latitude and longitude manually, or click the mini map to drop a pin and auto-fill both fields.")

    geo_col1, geo_col2 = st.columns(2)
    geo_lat = geo_col1.text_input("Latitude", key="geo_lat")
    geo_lon = geo_col2.text_input("Longitude", key="geo_lon")
    st.session_state["geo_lat_value"] = geo_lat
    st.session_state["geo_lon_value"] = geo_lon

    try:
        map_lat = float(st.session_state["geo_lat_value"])
        map_lon = float(st.session_state["geo_lon_value"])
    except ValueError:
        map_lat = 20.0
        map_lon = 0.0

    mini_map = folium.Map(
        location=[map_lat, map_lon],
        zoom_start=2,
        tiles=None,
        world_copy_jump=False,
        max_bounds=True,
        min_lat=-85,
        max_lat=85,
        min_lon=-180,
        max_lon=180,
    )
    folium.TileLayer(
        tiles="CartoDB positron",
        attr="&copy; OpenStreetMap contributors &copy; CARTO",
        no_wrap=True,
    ).add_to(mini_map)
    folium.CircleMarker(
        location=[map_lat, map_lon],
        radius=8,
        color="#d62828",
        weight=2,
        fill=True,
        fill_color="#f77f00",
        fill_opacity=0.85,
        tooltip="Selected coordinates",
    ).add_to(mini_map)
    map_result = st_folium(
        mini_map,
        key="geo_picker_map",
        height=300,
        returned_objects=["last_clicked"],
        use_container_width=True,
        on_change=_apply_geo_picker_selection,
        wrap_longitude=False,
    )
    if map_result and map_result.get("last_clicked"):
        selected = map_result["last_clicked"]
        st.caption(f"Selected on map: {selected['lat']:.6f}, {selected['lng']:.6f}")

    col1, col2, col3 = st.columns(3)
    event_id = col1.text_input("Event ID", value=str(uuid4()))
    account_id = col2.text_input("Account ID", value="ACC1000001")
    instrument_id = col3.text_input("Instrument ID", value="CARD5000001")

    col4, col5, col6, col7 = st.columns(4)
    event_date = col4.date_input("Event Date", value=date(2026, 6, 2))
    event_time = col5.time_input("Event Time", value=time(9, 15, 0))
    amount = col6.number_input("Amount", min_value=1.0, value=850.0, step=50.0)
    mcc = col7.text_input("MCC", value="5411")

    col8, col9, col10 = st.columns(3)
    country = col8.selectbox("Country", options=COUNTRY_CODES, index=COUNTRY_CODES.index("IN"))
    ip = col9.text_input("IP", value="49.43.12.110")
    device_fingerprint = col10.text_input("Device Fingerprint", value="devfp-0a91cd73")

    col11, col12, col13 = st.columns(3)
    merchant_id = col11.text_input("Merchant ID", value="MERGROC-210")
    entry_mode = col12.text_input("Entry Mode", value="CHIP")
    terminal_id = col13.text_input("Terminal ID", value="TERM-2101")

    txn_type = st.text_input("Transaction Type", value="PURCHASE")
    submit = st.button("Submit", type="primary")

    if submit:
        try:
            geo_coordinates = [
                float(st.session_state["geo_lat_value"]),
                float(st.session_state["geo_lon_value"]),
            ]
        except (TypeError, ValueError):
            st.error("Latitude and Longitude must be valid decimal numbers.")
            return

        event_ts = datetime.combine(event_date, event_time).isoformat()
        payload = {
            "event_id": event_id,
            "event_ts": event_ts,
            "account_id": account_id,
            "instrument_id": instrument_id,
            "amount": float(amount),
            "currency": "INR",
            "country": country,
            "mcc": mcc,
            "merchant_id": merchant_id,
            "entry_mode": entry_mode,
            "ip": ip,
            "device_fingerprint": device_fingerprint,
            "terminal_id": terminal_id,
            "txn_type": txn_type,
            "geo_coordinates": geo_coordinates,
        }
        try:
            response = requests.post(f"{api_base.rstrip('/')}/score-behavior", json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            error_detail = ""
            response_obj = getattr(exc, "response", None)
            if response_obj is not None:
                error_detail = response_obj.text
            st.error(f"API request failed: {exc}")
            if error_detail:
                st.code(error_detail)
            return

        score_col, change_col = st.columns(2)
        score_col.metric("Behavior Score", result["behavior_score"])
        change_col.metric("Behavior Change", str(result["behavior_change"]))
        if result["behavior_change"]:
            st.error(f"Flagged: {', '.join(result['reasons']) or 'No reasons returned'}")
        else:
            st.success("Transaction evaluated as normal.")
        st.json(result)


def render_bulk_simulator_controller() -> None:
    st.subheader("Bulk Simulator Controller")
    col1, col2 = st.columns(2)
    customers = col1.slider("Number of Customers", min_value=1, max_value=50, value=5)
    months = col2.slider("Months of Baseline Data", min_value=3, max_value=6, value=4)

    col3, col4, col5 = st.columns(3)
    inject_time_shift = col3.toggle("Inject Time Shift", value=True)
    inject_amount_spike = col4.toggle("Inject Large Amount Spike", value=False)
    inject_new_ip = col5.toggle("Inject New IP Usage", value=False)

    action_col1, action_col2 = st.columns(2)

    if action_col1.button("Run Simulation", type="primary"):
        try:
            summary = run_generation_script(
                customers=customers,
                months=months,
                inject_time_shift=inject_time_shift,
                inject_amount_spike=inject_amount_spike,
                inject_new_ip=inject_new_ip,
            )
            run_scoring = any([inject_time_shift, inject_amount_spike, inject_new_ip])
            pipeline = run_post_generation_pipeline(run_scoring=run_scoring)
        except subprocess.CalledProcessError as exc:
            st.error(exc.stdout or exc.stderr or "Simulation failed.")
            return
        except Exception as exc:
            st.error(f"Simulation failed: {exc}")
            return

        st.success(f"Generated {summary['total_transactions']} records for {summary['customers']} customer(s).")
        st.json(summary)
        with st.expander("Post-generation pipeline output"):
            st.text(pipeline["feature_output"])
            if pipeline["score_output"]:
                st.text(pipeline["score_output"])
            else:
                st.info("Scoring skipped because all anomaly toggles were turned off.")

    if action_col2.button("Clear History"):
        try:
            clear_behavior_history()
        except Exception as exc:
            st.error(f"Failed to clear history: {exc}")
            return

        st.success("Cleared raw_transactions, behavioral_profiles, and scoring_results.")


def render_metrics_and_visualization() -> None:
    st.subheader("Metrics & Outlier Visualization")
    try:
        transactions, profiles, scoring = load_visualization_data()
    except Exception as exc:
        st.error(f"Failed to load database data: {exc}")
        return

    if transactions.empty:
        st.info("No transaction data available yet.")
        return

    transactions["event_ts"] = pd.to_datetime(transactions["event_ts"], utc=False)
    transactions["event_id"] = transactions["event_id"].astype(str)
    transactions["account_id"] = transactions["account_id"].astype(str)
    transactions["country"] = transactions["country"].astype(str)
    transactions["mcc"] = transactions["mcc"].astype(str)
    transactions["behavior_change"] = transactions["behavior_change"].fillna(False)
    transactions["behavior_label"] = transactions["behavior_change"].map({True: "Anomaly", False: "Normal"})
    transactions["behavior_reasons"] = transactions["behavior_reasons"].apply(parse_reason_array)
    scoring["event_id"] = scoring["event_id"].astype(str)
    if "account_id" in profiles.columns:
        profiles["account_id"] = profiles["account_id"].astype(str)

    account_options = sorted(transactions["account_id"].astype(str).unique().tolist())
    selected_account = st.selectbox("Account", options=account_options, index=0)
    filtered_txns = transactions.loc[transactions["account_id"].astype(str) == selected_account].copy()
    filtered_profiles = profiles.loc[profiles["account_id"].astype(str) == selected_account].copy()

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Transactions", len(filtered_txns))
    metric2.metric("Flagged Anomalies", int(filtered_txns["behavior_change"].sum()))
    metric3.metric("Average Amount", round(float(filtered_txns["amount"].mean()), 2))

    scatter = px.scatter(
        filtered_txns,
        x="event_ts",
        y="amount",
        color="behavior_label",
        color_discrete_map={"Normal": "green", "Anomaly": "red"},
        title="Transaction Amounts Over Time",
        hover_data=["event_id", "behavior_score"],
    )
    st.plotly_chart(scatter, width="stretch")

    deviation_chart = go.Figure()
    deviation_chart.add_trace(
        go.Scatter(
            x=filtered_txns["event_ts"],
            y=filtered_txns["amount"],
            mode="markers",
            marker=dict(
                color=filtered_txns["behavior_label"].map({"Normal": "green", "Anomaly": "red"}),
                size=9,
            ),
            name="Transactions",
        )
    )

    if not filtered_profiles.empty:
        avg_amount = float(filtered_profiles.iloc[0]["avg_amount"])
        std_amount = float(filtered_profiles.iloc[0]["std_amount"])
        for multiplier, color in [(0, "blue"), (1, "orange"), (2, "gold"), (3, "red")]:
            upper = avg_amount + multiplier * std_amount
            lower = max(avg_amount - multiplier * std_amount, 0)
            deviation_chart.add_hline(y=upper, line_dash="dash", line_color=color)
            if multiplier > 0:
                deviation_chart.add_hline(y=lower, line_dash="dash", line_color=color)

    deviation_chart.update_layout(title="Amount Deviation Bands (Z-score View)", xaxis_title="Timestamp", yaxis_title="Amount")
    st.plotly_chart(deviation_chart, width="stretch")

    reason_rows = []
    for reasons in transactions["behavior_reasons"]:
        for reason in reasons:
            reason_rows.append({"reason": reason})
    reasons_df = pd.DataFrame(reason_rows)
    if reasons_df.empty:
        st.info("No behavior reasons recorded yet.")
    else:
        reason_counts = reasons_df["reason"].value_counts().reset_index()
        reason_counts.columns = ["reason", "count"]
        reasons_chart = px.bar(reason_counts, x="reason", y="count", title="Behavior Reasons Distribution")
        st.plotly_chart(reasons_chart, width="stretch")

    with st.expander("Behavioral Profiles"):
        st.dataframe(filtered_profiles, width="stretch")
    with st.expander("Scoring Results"):
        st.dataframe(scoring, width="stretch")


def main() -> None:
    st.title("Behavioral Anomaly Detection Testing UI")
    tabs = st.tabs(
        [
            "Single Transaction Tester",
            "Bulk Simulator Controller",
            "Metrics & Outlier Visualization",
        ]
    )

    with tabs[0]:
        render_single_transaction_tester()
    with tabs[1]:
        render_bulk_simulator_controller()
    with tabs[2]:
        render_metrics_and_visualization()


if __name__ == "__main__":
    main()
