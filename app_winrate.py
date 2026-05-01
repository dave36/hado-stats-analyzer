import streamlit as st
import pandas as pd
import plotly.express as px

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------
st.set_page_config(
    page_title="Hado Stats",
    layout="wide"
)

# --------------------------------------------------
# CARGA DE DATOS
# --------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_excel("hado_stats_all.xlsx")

df = load_data()
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Funcion para colorear filas de MVP
def highlight_mvp(row):
    if row.get("MVP", False):
        return ["background-color: gold"] * len(row)
    return [""] * len(row)

# Funcion para contabilizar ganadores
def get_winner(row):
    if row["ScoreTeamRed"] > row["ScoreTeamBlue"]:
        return "Red"
    elif row["ScoreTeamBlue"] > row["ScoreTeamRed"]:
        return "Blue"
    else:
        return "Draw"

df["WinnerTeam"] = df.apply(get_winner, axis=1)


# --------------------------------------------------
# DETECCIÓN DE ROL (SIN TOCAR EXCEL)
# --------------------------------------------------
def detect_role(row):
    # Escudos (Tank)
    if row["BarrierStrength"] == 5:
        return "Escudos"

    # Spammer
    if row["ChargeSpeed"] >= 4:
        return "Spammer"

    # Tirador
    if row["BulletScale"] >= 4 or row["BulletSpeed"] >= 4:
        return "Tirador"

    return "Otro"

df["Role"] = df.apply(detect_role, axis=1)

# --------------------------------------------------
# TABS
# --------------------------------------------------
tab_partido, tab_global = st.tabs(["📊 Partido", "📈 Global"])

# ==================================================
# TAB 1 — PARTIDO
# ==================================================
with tab_partido:
    st.header("📊 Estadísticas por partido")

    #match_ids = sorted(df["timestamp"].unique())
    #selected_match = st.selectbox("Selecciona un partido", match_ids)
    
    # Tabla de partidos (uno por MatchId y timestamp)
    matches = (
        df[["MatchId", "timestamp"]]
        .drop_duplicates()
        .sort_values("timestamp", ascending=False)
    )

    # Texto legible para el selectbox
    matches["label"] = matches.apply(
        lambda x: f"{x['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}",
        axis=1
    )
    
    selected_label = st.selectbox(
        "Selecciona un partido",
        matches["label"]
    )

    # Recuperamos el MatchId real
    selected_match = matches.loc[
        matches["label"] == selected_label,
        "MatchId"
    ].iloc[0]

    match_df = df[df["MatchId"] == selected_match]

    # Resultado
    score_red = match_df["ScoreTeamRed"].iloc[0]
    score_blue = match_df["ScoreTeamBlue"].iloc[0]

    st.subheader("🏁 Resultado final")
    col_r, col_b = st.columns(2)
    col_r.metric("🔴 Rojo", score_red)
    col_b.metric("🔵 Azul", score_blue)

    # ------------------------
    # TABLAS POR EQUIPO
    # ------------------------
    st.subheader("Estadísticas por equipo")

    cols_to_show = [
        "PlayerId",
        "BrokenPlayer",   # kills
        "Out",            # muertes
        "InvokeSkills",    # bolas tiradas
        "MVP"
    ]

    col_red, col_blue = st.columns(2)

    with col_red:
        st.markdown("### 🔴 Equipo Rojo")
        red_df = match_df[match_df["Team"] == "Red"][cols_to_show]
        st.dataframe(
        red_df
        .rename(columns={
            "BrokenPlayer": "Kills",
            "Out": "Muertes",
            "InvokeSkills": "Bolas tiradas"
        })
        .style.apply(highlight_mvp, axis=1),
        use_container_width=True
    )

    with col_blue:
        st.markdown("### 🔵 Equipo Azul")
        blue_df = match_df[match_df["Team"] == "Blue"][cols_to_show]
        st.dataframe(
        blue_df
        .rename(columns={
            "BrokenPlayer": "Kills",
            "Out": "Muertes",
            "InvokeSkills": "Bolas tiradas"
        })
        .style.apply(highlight_mvp, axis=1),
        use_container_width=True
        )

    # ------------------------
    # BOLAS TIRADAS POR EQUIPO
    # ------------------------
    st.subheader("Bolas tiradas por equipo")

    team_shots = (
        match_df
        .groupby("Team")["InvokeSkills"]
        .sum()
        .reset_index()
        .rename(columns={"InvokeSkills": "Total bolas"})
    )

    st.bar_chart(team_shots.set_index("Team"))


    # Añadir rol al dataframe de la partida
    role_df = match_df.copy()
    role_df["Rol"] = role_df.apply(detect_role, axis=1)

    role_order = ["Spammer", "Escudos", "Tirador"]

    def plot_role_comparison(df, metric, title):
        plot_df = (
            df[df["Rol"].isin(role_order)]
            .groupby(["Rol", "Team", "PlayerId"])[metric]
            .sum()
            .reset_index()
            .pivot(index="Rol", columns="PlayerId", values=metric)
            .reindex(role_order)
        )

        st.markdown(f"### {title}")
        st.bar_chart(plot_df)

    # Métricas a comparar
    role_metrics = {
        "HitSkillsToBarrier": "Daño a escudos",
        "BrokenLifes": "Daño a pétalos",
        "InvokeBarriers": "Escudos utilizados",
        "ActiveBarrierMillisecond": "Duración escudos (ms)"
    }

    # Agrupamos por rol (suma, porque son acciones acumuladas)
    role_grouped = (
        role_df
        .groupby("Rol")[list(role_metrics.keys())]
        .sum()
        .reset_index()
    )

    # Orden lógico de roles
    role_order = ["Spammer", "Escudos", "Tirador"]
    role_grouped["Rol"] = pd.Categorical(
        role_grouped["Rol"],
        categories=role_order,
        ordered=True
    )
    role_grouped = role_grouped.sort_values("Rol")

    # ------------------------
    # GRID 2x2 DE GRÁFICOS
    # ------------------------
    st.subheader("Comparativa por rol")

    col1, col2 = st.columns(2)

    with col1:
        plot_role_comparison(
            role_df,
            "HitSkillsToBarrier",
            "Daño a escudos"
        )

        plot_role_comparison(
            role_df,
            "InvokeBarriers",
            "Escudos utilizados"
        )

    with col2:
        plot_role_comparison(
            role_df,
            "BrokenLifes",
            "Daño a pétalos"
        )

        plot_role_comparison(
            role_df,
            "ActiveBarrierMillisecond",
            "Duración de escudos (ms)"
        )

    # ------------------------
    # COMPARATIVA DE MOVIMIENTO Y TIEMPOS
    # ------------------------
    st.subheader("Comparativa de recarga")

    stats_df = match_df[[
        "PlayerId",
        "ChargeMillisecond",
        "EmptyMillisecond"
    ]].set_index("PlayerId")

    stats_df = stats_df.rename(columns={
        "ChargeMillisecond": "Tiempo recarga (ms)",
        "EmptyMillisecond": "Tiempo vacío (ms)"
    })

    st.bar_chart(stats_df)

    # ------------------------
    # PIE DE PÁGINA
    # ------------------------
    st.caption(
        "Kills = jugadores eliminados | "
        "Muertes = veces eliminado (Out) | "
        "Bolas tiradas = InvokeSkills"
    )

# ==================================================
# TAB 2 — GLOBAL
# ==================================================
with tab_global:
    st.header("📈 Estadísticas globales")

    # -----------------------------
    # FILTROS
    # -----------------------------
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        players = sorted(df["PlayerId"].unique())
        selected_players = st.multiselect(
            "Filtrar jugadores",
            players,
            default=players
        )

    with col_f2:
        roles = sorted(df["Role"].unique())
        selected_roles = st.multiselect(
            "Filtrar por rol",
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
    st.subheader("📊 Medias por jugador")

    numeric_cols = [
        "InvokeSkills",
        "HitSkillsToBarrier",
        "BrokenLifes",
        "InvokeBarriers",
        "ActiveBarrierMillisecond",
        "MoveDistance",
        "EmptyMillisecond",
        "ChargeMillisecond",
        "Out"
    ]

    # CALCULO DE WINRATE
    # Una fila por jugador / rol / partido
    player_matches = (
        global_df[
            ["PlayerId", "Role", "MatchId", "Team", "WinnerTeam"]
        ]
        .drop_duplicates()
    )

    # Victoria si el equipo del jugador coincide con el ganador
    player_matches["Win"] = (
        player_matches["Team"] == player_matches["WinnerTeam"]
    )

    # Winrate por jugador y rol
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

    # Nos quedamos solo con lo que queremos mostrar
    winrate_df = winrate_df[["PlayerId", "Role", "Winrate (%)"]]

    # Creacion de la tabla
    means_df = (
        global_df
        .groupby(["PlayerId", "Role"])[numeric_cols]
        .mean()
        .round(2)
        .reset_index()
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
        title="MVPs por jugador"
    )
    st.plotly_chart(fig_mvp, use_container_width=True)

    # -----------------------------
    # DAÑO TOTAL
    # -----------------------------
    st.subheader("💥 Daño total (BrokenLifes)")

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
        title="Daño total acumulado"
    )
    st.plotly_chart(fig_dmg, use_container_width=True)

    # -----------------------------
    # MOVIMIENTO
    # -----------------------------
    st.subheader("🏃 Distancia recorrida")

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
        title="Distancia total recorrida"
    )
    st.plotly_chart(fig_move, use_container_width=True)

    # -----------------------------
    # VALIDACIÓN DE ROLES
    # -----------------------------
    st.subheader("🧠 Rol detectado (control)")

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

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.markdown("---")
st.caption("Hado Stats Dashboard · Streamlit")
