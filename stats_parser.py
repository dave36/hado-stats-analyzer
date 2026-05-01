import re
import json
import pandas as pd

def parse_stats_log(stats_log_path, mapping):

    log_pattern = re.compile(
        r'^(?P<timestamp>\S+) .*?PlayerLog: (?P<json>\{.*\})$'
    )

    rows = []
    match_counter = 0

    with open(stats_log_path, "r", encoding="utf-8") as f:
        for line in f:

            match = log_pattern.search(line)
            if not match:
                continue

            timestamp = match.group("timestamp")

            outer_json = json.loads(match.group("json"))
            event_name = outer_json.get("eventName")

            if event_name != "End":
                continue

            data = json.loads(outer_json["jsonData"])

            player_logs = data.get("playerLogs", [])
            result_score = data.get("resultScore", [])
            mvp_id = data.get("mvpPlayerId")

            score_red = next(
                (t["score"] for t in result_score if t["name"] == "Red"),
                None
            )
            score_blue = next(
                (t["score"] for t in result_score if t["name"] == "Blue"),
                None
            )

            match_counter += 1
            match_id = f"Match_{match_counter:04d}"

            n_players = len(player_logs)
            n_team_red = n_players // 2

            for idx, player in enumerate(player_logs):

                socket = player.get("PlayerId")

                name = mapping.get(socket, {}).get("name", socket)
                team = mapping.get(socket, {}).get("team")

                row = dict(player)

                row["PlayerId"] = name
                row["Team"] = team or ("Red" if idx < n_team_red else "Blue")
                row["MatchId"] = match_id
                row["timestamp"] = timestamp
                row["MVP"] = (socket == mvp_id)
                row["ScoreTeamRed"] = score_red
                row["ScoreTeamBlue"] = score_blue

                rows.append(row)

    return pd.DataFrame(rows)