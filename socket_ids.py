import json
import re

LOG_FILE = "socket-event.log"   # <-- tu fichero
OUTPUT_CSV = "player_socket_ids.csv"

socket_ids = {}

def get_ids(LOG_FILE):
    # Captura SOLO líneas ON DeviceInfo
    pattern = re.compile(r'ON DeviceInfo:\s*(\{.*\})')

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if not match:
                continue

            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

            config = data.get("config", {})
            socket_id = data.get("socketId")

            if not socket_id:
                continue

            # Filtros clave
            if config.get("id") == "Audience":
                continue

            team_id = config.get("teamId", 0)
            if team_id not in (1, 2):
                continue

            socket_ids[socket_id] = {
                "socketId": socket_id,
                "teamId": team_id,
                "groupId": config.get("groupId"),
                "name": config.get("name")
            }
    return socket_ids

# ------------------------
# RESULTADO
# ------------------------
socket_ids = get_ids(LOG_FILE)
print("Socket IDs de jugadores encontrados:")
for p in socket_ids.values():
    print(p["teamId"])
    print(p["name"])

# ------------------------
# EXPORTAR A CSV
# ------------------------
if socket_ids:
    import csv

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["socketId", "teamId", "groupId", "name"]
        )
        writer.writeheader()
        writer.writerows(socket_ids.values())

    print(f"\nCSV generado: {OUTPUT_CSV}")
else:
    print("\n⚠️ No se encontraron jugadores")
