# worker_condition_dashboard.py
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# --- Step 1: Load CSV without headers ---
file_path = r"C:\Users\admin\Documents\DongXu Projects\Worker_Condition_2026-Jan-March_(DirectExport).csv"
temp_cols = ["Number", "Station", "Duplicate", "Distance", "Status_ID", "DateTime"]
df = pd.read_csv(file_path, header=None, names=temp_cols)

# Drop unnecessary columns
df = df.drop(columns=["Number", "Duplicate"])
df = df[["Station", "Distance", "Status_ID", "DateTime"]]

# Convert types
df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce")
df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

st.title("Workstation Condition Dashboard")

# --- Step 2: Sidebar filters ---
st.sidebar.header("Filters")
stations = df["Station"].unique()
selected_station = st.sidebar.selectbox("Select Station", stations, key="station_select")

filtered_df = df[df["Station"] == selected_station].copy()

min_date = filtered_df["DateTime"].dt.date.min()
max_date = filtered_df["DateTime"].dt.date.max()

selected_date = st.sidebar.date_input(
    "Select Date",
    min_date,
    min_value=min_date,
    max_value=max_date,
    key="date_select"
)

filtered_df = filtered_df[filtered_df["DateTime"].dt.date == selected_date]
filtered_df = filtered_df.sort_values("DateTime").reset_index(drop=True)

# --- Step 3: Debounce Logic ---
if not filtered_df.empty:
    raw_status = (filtered_df["Distance"] < 50).astype(int)
    debounced_status = []
    current_status = raw_status.iloc[0]
    count = 0
    debounce_0_to_1 = 5  # 0→1
    debounce_1_to_0 = 3  # 1→0

    for s in raw_status:
        if current_status == 0 and s == 1:
            count += 1
            if count >= debounce_0_to_1:
                current_status = 1
                count = 0
        elif current_status == 1 and s == 0:
            count += 1
            if count >= debounce_1_to_0:
                current_status = 0
                count = 0
        else:
            count = 0
        debounced_status.append(current_status)

    filtered_df.insert(2, "Status", debounced_status)

    # --- Step 4: Detect Sensor Outage (Status = 2 if gap > 30s) ---
    filtered_df["TimeDiff"] = filtered_df["DateTime"].diff().dt.total_seconds()
    fault_active = False
    for i in range(len(filtered_df)):
        if i > 0 and filtered_df["TimeDiff"].iloc[i] > 30:
            fault_active = True
            filtered_df.at[i - 1, "Status"] = 2
        if fault_active:
            filtered_df.at[i, "Status"] = 2
        if fault_active and i > 0 and filtered_df["TimeDiff"].iloc[i] <= 30:
            fault_active = False

# --- Step 5: Statistics (time-based) ---
st.sidebar.header("Statistics")
if not filtered_df.empty and len(filtered_df) > 1:
    filtered_df["TimeDiff"] = filtered_df["DateTime"].diff().dt.total_seconds().fillna(0)
    filtered_df.at[len(filtered_df)-1, "TimeDiff"] = filtered_df["TimeDiff"].iloc[-2]

    total_active = filtered_df.loc[filtered_df["Status"] == 1, "TimeDiff"].sum()
    total_inactive = filtered_df.loc[filtered_df["Status"] == 0, "TimeDiff"].sum()
    total_fault = filtered_df.loc[filtered_df["Status"] == 2, "TimeDiff"].sum()
    total_valid = total_active + total_inactive
    percentage_active = (total_active / total_valid) * 100 if total_valid > 0 else 0

    def sec_to_hms(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    st.sidebar.markdown(f"**Total Active:** {sec_to_hms(total_active)}")
    st.sidebar.markdown(f"**Total Inactive:** {sec_to_hms(total_inactive)}")
    st.sidebar.markdown(f"**Sensor Fault:** {sec_to_hms(total_fault)}")
    st.sidebar.markdown(f"**Percentage Active (excluding fault):** {percentage_active:.2f}%")
else:
    st.sidebar.markdown("No data available for selected filters.")

# --- Step 6: Step Chart (Original Style + Colored Legend Font) ---
if not filtered_df.empty:
    color_map = {0: "red", 1: "green", 2: "blue"}
    fig = go.Figure()

    # Main step trace
    fig.add_trace(
        go.Scatter(
            x=filtered_df["DateTime"],
            y=filtered_df["Status"],
            mode="lines",
            line=dict(shape="hv", width=2),
            hovertemplate=(
                "Time: %{x}<br>"
                "Status: %{y}<br>"
                "Distance: %{customdata[0]}<br>"
                "Status_ID: %{customdata[1]}"
            ),
            customdata=filtered_df[["Distance", "Status_ID"]].values,
            showlegend=False
        )
    )

    # Dummy traces for legend with colored font
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                             line=dict(color="green", width=3),
                             name="<span style='color:green'>1 = Active</span>"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                             line=dict(color="red", width=3),
                             name="<span style='color:red'>0 = Inactive</span>"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                             line=dict(color="blue", width=3),
                             name="<span style='color:blue'>2 = Offline</span>"))

    fig.update_layout(
        title=f"Workstation Condition Step Chart for {selected_station} on {selected_date}",
        xaxis_title="Slider",
        yaxis=dict(tickmode="array", tickvals=[0, 1, 2]),
        legend=dict(
            x=1.02,
            y=1,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black",
            borderwidth=1
        ),
        hovermode="x unified",
        xaxis=dict(
            rangeslider=dict(
                visible=True,
                thickness=0.15,
                bgcolor="lightgrey",
                bordercolor="black",
                borderwidth=1
            ),
            type="date",
            fixedrange=False
        ),
        uirevision="constant"
    )

    st.plotly_chart(fig, width="stretch")
else:
    st.info("No data available for the selected filters.")

# --- Step 7: Summary Table ---
st.subheader("Summary Table: All Workstations")
summary_df = df[df["DateTime"].dt.date == selected_date].groupby("Station").apply(
    lambda x: (x["Distance"] < 50).sum() / len(x) * 100 if len(x) > 0 else 0
).reset_index()
summary_df.columns = ["Station", "Percentage Active (%)"]
st.dataframe(summary_df)

# --- Step 8: Data Table ---
st.subheader("Data Table")
st.dataframe(filtered_df)