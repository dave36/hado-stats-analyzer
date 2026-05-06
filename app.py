# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import tempfile
import os
import zipfile

from main import parse_logs_and_build_dataframe

# Helper for ZIP uploads

def locate_log_files_in_zip(zip_file):
    log_members = [m for m in zip_file.namelist() if m.lower().endswith(".log")]
    if len(log_members) != 2:
        return None, None

    socket_member = None
    stats_member = None

    for member in log_members:
        try:
            with zip_file.open(member) as source:
                for line in source:
                    if b"ON DeviceInfo:" in line:
                        socket_member = member
                        break
                    if b"EMIT PlayerLog:" in line:
                        stats_member = member
                        break
        except Exception:
            continue

    if socket_member and stats_member:
        return socket_member, stats_member

    # Fallback: if exactly two .log files, use them in order
    return log_members[0], log_members[1]


# Function to color MVP rows
def highlight_mvp(row):
    if row.get("MVP", False):
        return ["background-color: gold"] * len(row)
    return [""] * len(row)

# --------------------------------------------------
st.set_page_config(page_title="Hado Stats", layout="wide")

# --------------------------------------------------
# TABS
# --------------------------------------------------

tab_upload, tab_partido, tab_global, tab_editar = st.tabs(
    ["⬆️ Upload logs", "📊 Match", "📈 Global", "✏️ Edit Players"]
)

# ==================================================
# TAB UPLOAD
# ==================================================

with tab_upload:

    st.header("⬆️ Upload log files")

    zip_file = st.file_uploader(
        "Upload a ZIP containing both socket-event.log and stats.log",
        type=["zip"]
    )

    if zip_file is None:
        socket_file = st.file_uploader("socket-event.log", type=["log", "txt"])
        stats_file = st.file_uploader("stats.log", type=["log", "txt"])
    else:
        socket_file = None
        stats_file = None
        st.info("ZIP uploaded: individual log upload is disabled.")

    can_process = False
    if zip_file:
        can_process = True
    elif socket_file and stats_file:
        can_process = True

    if can_process:
        if st.button("Process logs"):
            with st.spinner("Processing..."):
                if zip_file:
                    try:
                        with zipfile.ZipFile(zip_file) as z:
                            socket_member, stats_member = locate_log_files_in_zip(z)

                            if not socket_member or not stats_member:
                                st.error(
                                    "The ZIP must contain exactly two .log files: one socket-event log and one stats log."
                                )
                                st.stop()

                            socket_file_like = z.open(socket_member)
                            stats_file_like = z.open(stats_member)
                    except zipfile.BadZipFile:
                        st.error("The ZIP file is invalid or corrupted.")
                        st.stop()
                else:
                    import io
                    socket_content = socket_file.getvalue().decode('utf-8')
                    stats_content = stats_file.getvalue().decode('utf-8')
                    socket_file_like = io.StringIO(socket_content)
                    stats_file_like = io.StringIO(stats_content)

                df = parse_logs_and_build_dataframe(
                    socket_file_like,
                    stats_file_like
                )

                st.session_state["df"] = df
                st.success("Logs processed successfully")

# ==================================================
# USO DEL DATAFRAME
# ==================================================

if "df" not in st.session_state:
    st.info("Upload the logs first")
    st.stop()

df = st.session_state["df"]

if df.empty or "timestamp" not in df.columns:
    st.error("The processed logs do not contain valid match data. Make sure the log files include 'End' events.")
    st.stop()

# ==================================================
# ROLE DETECTION
# ==================================================

def detect_role(row):
    barrier = row.get("BarrierStrength", 0)
    charge = row.get("ChargeSpeed", 0)
    scale = row.get("BulletScale", 0)
    speed = row.get("BulletSpeed", 0)
    if barrier == 5:
        return "Shield"
    if charge == 4:
        return "Technician"
    if scale >= 4 or speed >= 4:
        return "Attacker"
    if charge == 3 and speed == 3 and scale == 3:
        return "Default"
    return "Other"


df["Role"] = df.apply(lambda r: detect_role(r), axis=1)

# --------------------------------------------------
# WINNER TEAM
# --------------------------------------------------

def get_winner(row):
    if row["ScoreTeamRed"] > row["ScoreTeamBlue"]:
        return "Red"
    if row["ScoreTeamBlue"] > row["ScoreTeamRed"]:
        return "Blue"
    return "Draw"


df["WinnerTeam"] = df.apply(get_winner, axis=1)

# ==================================================
# TAB PARTIDO
# ==================================================

with tab_partido:

    st.header("📊 Match Statistics")

    # Match table (one per MatchId)
    matches = (
        df[["MatchId", "timestamp"]]
        .drop_duplicates()
        .sort_values("timestamp", ascending=False)
    )

    # Readable text for selectbox
    from datetime import datetime
    matches["label"] = matches.apply(
        lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S'),
        axis=1
    )
    
    selected_label = st.selectbox(
        "Select a match",
        matches["label"]
    )

    # Recuperamos el MatchId real
    selected_match = matches.loc[
        matches["label"] == selected_label,
        "MatchId"
    ].iloc[0]

    match_df = df[df["MatchId"] == selected_match]

    # Result
    score_red = match_df["ScoreTeamRed"].iloc[0]
    score_blue = match_df["ScoreTeamBlue"].iloc[0]

    st.subheader("🏁 Final Result")
    col_r, col_b = st.columns(2)
    col_r.metric("🔴 Red", score_red)
    col_b.metric("🔵 Blue", score_blue)

    # ------------------------
    # TEAM TABLES
    # ------------------------
    st.subheader("Team Statistics")

    cols_to_show = [
        "PlayerId",
        "Role",
        "BrokenPlayer",   # kills
        "Out",            # deaths
        "InvokeSkills",    # balls thrown
        "MVP"
    ]

    col_red,col_blue = st.columns(2)

    with col_red:
        st.markdown("### 🔴 Red Team")
        red_df = match_df[match_df["Team"] == "Red"][cols_to_show]
        st.dataframe(
        red_df
        .rename(columns={
            "BrokenPlayer": "Kills",
            "Out": "Deaths",
            "InvokeSkills": "Balls thrown"
        })
        .style.apply(highlight_mvp, axis=1),
        use_container_width=True
    )

    with col_blue:
        st.markdown("### 🔵 Blue Team")
        blue_df = match_df[match_df["Team"] == "Blue"][cols_to_show]
        st.dataframe(
        blue_df
        .rename(columns={
            "BrokenPlayer": "Kills",
            "Out": "Deaths",
            "InvokeSkills": "Balls thrown"
        })
        .style.apply(highlight_mvp, axis=1),
        use_container_width=True
        )
        


    # ------------------------
    # BALLS THROWN BY TEAM
    # ------------------------
    st.subheader("Balls thrown by team")

    team_shots = (
    match_df
    .groupby("Team")["InvokeSkills"]
    .sum()
    .reset_index()
    .rename(columns={"InvokeSkills": "Total balls"})
)

    # Forzar orden: Red primero, Blue después
    team_shots["Team"] = pd.Categorical(
        team_shots["Team"],
        categories=["Red", "Blue"],
        ordered=True
    )

    team_shots = team_shots.sort_values("Team")

    st.bar_chart(team_shots.set_index("Team"))

    # Function to detect role
    def detect_role(row):
        if (
            row["BulletSpeed"] == 1 and
            row["BulletScale"] == 1 and
            row["ChargeSpeed"] == 3 and
            row["BarrierStrength"] == 5
        ):
            return "Shield"

        if (
            row["BulletSpeed"] == 3 and
            row["BulletScale"] == 2 and
            row["ChargeSpeed"] == 4 and
            row["BarrierStrength"] == 1
        ):
            return "Technician"

        if (
            (row["BulletSpeed"] == 3 and row["BulletScale"] == 5 and row["ChargeSpeed"] == 1 and row["BarrierStrength"] == 1) or
            (row["BulletSpeed"] == 4 and row["BulletScale"] == 4 and row["ChargeSpeed"] == 1 and row["BarrierStrength"] == 1)
        ):
            return "Attacker"

        return "Otro"

    # Add role to the match dataframe
    role_df = match_df.copy()
    role_df["Role"] = role_df.apply(detect_role, axis=1)

    role_order = ["Shield", "Technician", "Attacker"]

    def plot_role_comparison(df, metric, title):
        plot_df = (
            df[df["Role"].isin(role_order)]
            .groupby(["Role", "Team", "PlayerId"])[metric]
            .sum()
            .reset_index()
            .pivot(index="Role", columns="PlayerId", values=metric)
            .reindex(role_order)
        )

        st.markdown(f"### {title}")
        st.bar_chart(plot_df)

    # Métricas a comparar
    role_metrics = {
        "HitSkillsToBarrier": "Shield damage",
        "BrokenLifes": "Broken lifes",
        "InvokeBarriers": "Shields used",
        "ActiveBarrierMillisecond": "Shield duration (ms)"
    }

    # Group by role (sum, because they are accumulated actions)
    role_grouped = (
        role_df
        .groupby("Role")[list(role_metrics.keys())]
        .sum()
        .reset_index()
    )

    # Logical order of roles
    role_order = ["Shield", "Technician", "Attacker"]
    role_grouped["Role"] = pd.Categorical(
        role_grouped["Role"],
        categories=role_order,
        ordered=True
    )
    role_grouped = role_grouped.sort_values("Role")

    # ------------------------
    # 2x2 GRID OF CHARTS
    # ------------------------
    st.subheader("Role Comparison")

    col1, col2 = st.columns(2)

    with col1:
        plot_role_comparison(
            role_df,
            "HitSkillsToBarrier",
            "Shield damage"
        )

        plot_role_comparison(
            role_df,
            "InvokeBarriers",
            "Shields used"
        )

    with col2:
        plot_role_comparison(
            role_df,
            "BrokenLifes",
            "Broken lifes"
        )

        plot_role_comparison(
            role_df,
            "ActiveBarrierMillisecond",
            "Shield duration (ms)"
        )

    # ------------------------
    # MOVEMENT AND TIMES COMPARISON
    # ------------------------
    st.subheader("Reload Comparison")

    stats_df = match_df[[
        "PlayerId",
        "ChargeMillisecond",
        "EmptyMillisecond"
    ]].set_index("PlayerId")

    stats_df = stats_df.rename(columns={
        "ChargeMillisecond": "Reload Time (ms)",
        "EmptyMillisecond": "Empty Time (ms)"
    })

    st.bar_chart(stats_df)

    # ------------------------
    # FOOTER
    # ------------------------
    st.caption(
        "Kills = players eliminated | "
        "Deaths = times eliminated (Out) | "
        "Balls thrown = InvokeSkills"
    )

# ==================================================
# TAB 2 — GLOBAL
# ==================================================
with tab_global:
    st.header("📈 Global Statistics")

    # -----------------------------
    # FILTERS
    # -----------------------------
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        players = sorted(df["PlayerId"].unique())
        selected_players = st.multiselect(
            "Filter players",
            players,
            default=players
        )

    with col_f2:
        roles = sorted(df["Role"].unique())
        selected_roles = st.multiselect(
            "Filter by role",
            roles,
            default=roles
        )

    global_df = df[
        (df["PlayerId"].isin(selected_players)) &
        (df["Role"].isin(selected_roles))
    ]

    # -----------------------------
    # MEDIAS POR JUGADOR
    # -----------------------------
    st.subheader("📊 Player Averages")

    numeric_cols = [
        "BrokenPlayer",
        "Out",
        "InvokeSkills",
        "HitSkillsToBarrier",
        "BrokenLifes",
        "InvokeBarriers",
        "ActiveBarrierMillisecond",
        "MoveDistance",
        "EmptyMillisecond",
        "ChargeMillisecond"
    ]

    player_matches = (
        global_df[
            ["PlayerId", "Role", "MatchId", "Team", "WinnerTeam"]
        ]
        .drop_duplicates()
    )

    player_matches["Win"] = (
        player_matches["Team"] == player_matches["WinnerTeam"]
    )

    winrate_df = (
        player_matches
        .groupby(["PlayerId", "Role"])
        .agg(
            Partidas_jugadas=("MatchId", "count"),
            Partidas_ganadas=("Win", "sum")
        )
        .reset_index()
    )

    winrate_df["Winrate (%)"] = (
        winrate_df["Partidas_ganadas"]
        / winrate_df["Partidas_jugadas"]
        * 100
    ).round(2)

    winrate_df = winrate_df[["PlayerId", "Role", "Winrate (%)"]]

    means_df = (
        global_df
        .groupby(["PlayerId", "Role"])[numeric_cols]
        .mean()
        .round(2)
        .reset_index()
        .rename(columns={"BrokenPlayer": "Kills"})
        .rename(columns={"Out": "Deaths"})
    )

    means_df = means_df.merge(
        winrate_df,
        on=["PlayerId", "Role"],
        how="left"
    )

    st.dataframe(means_df, use_container_width=True)

    # -----------------------------
    # MVPs
    # -----------------------------
    st.subheader("🏆 MVPs")

    mvp_df = (
        global_df[global_df["MVP"] == True]
        .groupby(["PlayerId", "Role"])
        .size()
        .reset_index(name="MVPs")
        .sort_values("MVPs", ascending=False)
    )

    fig_mvp = px.bar(
        mvp_df,
        x="PlayerId",
        y="MVPs",
        color="Role",
        hover_name="PlayerId",
        title="MVPs by player"
    )
    st.plotly_chart(fig_mvp, use_container_width=True)

    # -----------------------------
    # DAÑO TOTAL
    # -----------------------------
    st.subheader("💥 Total Damage (BrokenLifes)")

    dmg_df = (
        global_df
        .groupby(["PlayerId", "Role"])["BrokenLifes"]
        .sum()
        .reset_index()
        .sort_values("BrokenLifes", ascending=False)
    )

    fig_dmg = px.bar(
        dmg_df,
        x="PlayerId",
        y="BrokenLifes",
        color="Role",
        hover_name="PlayerId",
        title="Total damage accumulated"
    )
    st.plotly_chart(fig_dmg, use_container_width=True)

    # -----------------------------
    # MOVIMIENTO
    # -----------------------------
    st.subheader("🏃 Distance Traveled")

    move_df = (
        global_df
        .groupby(["PlayerId", "Role"])["MoveDistance"]
        .sum()
        .reset_index()
        .sort_values("MoveDistance", ascending=False)
    )

    fig_move = px.bar(
        move_df,
        x="PlayerId",
        y="MoveDistance",
        color="Role",
        hover_name="PlayerId",
        title="Total distance traveled"
    )
    st.plotly_chart(fig_move, use_container_width=True)

    # -----------------------------
    # ROLE VALIDATION
    # -----------------------------
    st.subheader("🧠 Detected Role (control)")

    st.dataframe(
        df[
            [
                "PlayerId",
                "BulletSpeed",
                "BulletScale",
                "ChargeSpeed",
                "BarrierStrength",
                "Role"
            ]
        ].drop_duplicates(),
        use_container_width=True
    )

# ==================================================
# TAB EDITAR JUGADORES
# ==================================================
with tab_editar:
    st.header("✏️ Edit Player Names")

    if "df" not in st.session_state:
        st.info("Upload the logs first")
        st.stop()

    df = st.session_state["df"]

    # -----------------------------
    # GLOBAL CHANGES
    # -----------------------------
    st.subheader("🔄 Global Changes")
    st.markdown("Change a name in **all** matches where it appears.")

    col_g1, col_g2, col_g3 = st.columns([3, 3, 2])

    with col_g1:
        global_old = st.selectbox(
            "Current name",
            sorted(df["PlayerId"].unique()),
            key="global_old"
        )

    with col_g2:
        global_new = st.text_input("New name", key="global_new")

    with col_g3:
        st.markdown("<br>", unsafe_allow_html=True)  # ajusta según necesites
        if st.button("Apply global"):
            if global_new.strip():
                df["PlayerId"] = df["PlayerId"].replace(global_old, global_new.strip())
                st.session_state["df"] = df
                st.success(f"Changed '{global_old}' to '{global_new}' in all matches")
                st.rerun()
            else:
                st.error("New name cannot be empty")

    st.markdown("---")

    # -----------------------------
    # EDITING BY MATCH
    # -----------------------------
    # DETAILED EDITING BY MATCH
    # -----------------------------
    st.subheader("🎯 Detailed editing by match")
    st.markdown("Edit specific names by match and player.")

    # Get unique combinations of MatchId, PlayerId, Team and Role
    unique_combinations = (
        df[["MatchId", "PlayerId", "Team", "Role"]]
        .drop_duplicates()
        .sort_values(["MatchId", "Team", "PlayerId"])
    )
    
    # Crear dataframe para edición
    edit_df = unique_combinations.copy()
    edit_df["New name"] = edit_df["PlayerId"]  # Prefill with current names

    # Reordenar columnas para mejor visualización
    edit_df = edit_df[["MatchId", "Team", "PlayerId", "Role", "New name"]]

    edited_df = st.data_editor(
        edit_df,
        use_container_width=True,
        disabled=["MatchId", "PlayerId", "Team", "Role"]  # Only allow editing the new name
    )

    if st.button("Apply detailed changes"):
        # Aplicar cambios usando merge
        df = df.merge(
            edited_df[["MatchId", "PlayerId", "New name"]],
            on=["MatchId", "PlayerId"],
            how="left"
        )
        
        # Update PlayerId with the new name where there is a change
        df["PlayerId"] = df["New name"].fillna(df["PlayerId"])
        
        # Limpiar columna temporal
        df = df.drop(columns=["New name"])
        
        # Actualizar session_state
        st.session_state["df"] = df
        
        st.success("Names updated successfully")
        st.rerun()  # Reload to reflect changes

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.markdown("---")

st.caption("Hado Stats Dashboard · Streamlit")