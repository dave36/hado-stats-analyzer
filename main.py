# main.py

import re
import json
import pandas as pd

# --------------------------------------------------
# SOCKET EVENT → SOCKET → {name, team}
# --------------------------------------------------

def extract_players_from_socket(socket_file_like):
    """
    socket_file_like: file-like object (e.g., from open() or zipfile.ZipFile.open())
    """
    pattern = re.compile(r'ON DeviceInfo:\s*(\{.*\})')
    mapping = {}

    for line in socket_file_like:
        line = line.decode('utf-8') if isinstance(line, bytes) else line
        m = pattern.search(line)
        if not m:
            continue

        try:
            data = json.loads(m.group(1))

            socket = data.get("socketId")
            config = data.get("config", {})

            name = config.get("name")
            team_id = config.get("teamId")

            if team_id == 1:
                team = "Red"
            elif team_id == 2:
                team = "Blue"
            else:
                team = None

            if socket and name:
                mapping[socket] = {
                    "name": name,
                    "team": team
                }
        except:
            pass

    return mapping


# --------------------------------------------------
# STATS LOG → EVENTS
# --------------------------------------------------

def parse_stats_log(stats_file_like, mapping):

    rows = []

    for line in stats_file_like:
        line = line.decode('utf-8') if isinstance(line, bytes) else line

        if "EMIT PlayerLog:" not in line:
            continue

        # Extract timestamp from the beginning of the line
        timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})', line)
        if not timestamp_match:
            continue
        timestamp = timestamp_match.group(1)

        # Extract JSON after "EMIT PlayerLog: "
        json_start = line.find('EMIT PlayerLog:') + len('EMIT PlayerLog:')
        json_str = line[json_start:].strip()

        try:
            data = json.loads(json_str)

            event_name = data.get("eventName")
            json_data = data.get("jsonData")

            if event_name == "End" and json_data:
                # Parse the nested jsonData
                end_data = json.loads(json_data)

                # Get team scores
                result_score = end_data.get("resultScore", [])
                score_team_red = None
                score_team_blue = None
                for team in result_score:
                    if team.get("name") == "Red":
                        score_team_red = team.get("score")
                    elif team.get("name") == "Blue":
                        score_team_blue = team.get("score")

                # Get MVP
                mvp_player_id = end_data.get("mvpPlayerId")

                # Process each player
                player_logs = end_data.get("playerLogs", [])
                for player_data in player_logs:
                    socket = player_data.get("PlayerId")

                    player_name = mapping.get(socket, {}).get("name", socket)
                    team = mapping.get(socket, {}).get("team")

                    row = {
                        "PlayerId": player_name,
                        "Team": team,
                        "MatchId": timestamp,  # Use timestamp as MatchId
                        "Score": player_data.get("Score"),
                        "MVP": 1 if socket == mvp_player_id else 0,

                        "InvokeSkills": player_data.get("InvokeSkills"),
                        "HitSkills": player_data.get("HitSkills"),
                        "HitSkillsToBarrier": player_data.get("HitSkillsToBarrier"),
                        "BrokenLifes": player_data.get("BrokenLifes"),
                        "BrokenPlayer": player_data.get("BrokenPlayer"),
                        "InvokeBarriers": player_data.get("InvokeBarriers"),
                        "ActiveBarrierMillisecond": player_data.get("ActiveBarrierMillisecond"),
                        "MoveDistance": player_data.get("MoveDistance"),
                        "Out": player_data.get("Out"),

                        "BulletSpeed": player_data.get("BulletSpeed"),
                        "BulletScale": player_data.get("BulletScale"),
                        "ChargeSpeed": player_data.get("ChargeSpeed"),
                        "BarrierStrength": player_data.get("BarrierStrength"),

                        "ChargeMillisecond": player_data.get("ChargeMillisecond"),
                        "EmptyMillisecond": player_data.get("EmptyMillisecond"),

                        "timestamp": timestamp,

                        "ScoreTeamRed": score_team_red,
                        "ScoreTeamBlue": score_team_blue
                    }

                    rows.append(row)

        except Exception as e:
            print(f"Error parsing line: {e}")
            pass

    return pd.DataFrame(rows)


# --------------------------------------------------
# FUNCIÓN MAESTRA
# --------------------------------------------------

def parse_logs_and_build_dataframe(socket_file_like, stats_file_like):

    mapping = extract_players_from_socket(socket_file_like)
    df = parse_stats_log(stats_file_like, mapping)
    return df