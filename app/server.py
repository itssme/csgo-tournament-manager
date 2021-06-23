import asyncio
import json
import logging
import os
import time
from functools import wraps

import aiorcon
from flask import Flask, request, render_template, redirect, Response
from flask_caching import Cache
from tqdm import tqdm

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.info("server running")

config = {
    "DEBUG": True,
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 30000
}

app = Flask(__name__, static_url_path="", static_folder="static")
app.config.from_mapping(config)
cache = Cache(app)


class RCONConnection:
    id = -1
    loop = None
    rcon = None


try:
    server_config = json.loads(open("config.json", "r").read())
    teams = json.loads(open("teams.json", "r").read())
except:
    logging.warning("Could not open config file in . context, trying app/config")
    server_config = json.loads(open("app/config.json", "r").read())
    teams = json.loads(open("app/teams.json", "r").read())

players = []
player_counter = 0
for team in teams:
    for player in team["players"]:
        player["id"] = player_counter
        players.append(player)
        player_counter += 1

os.makedirs(f"configs", exist_ok=True)

# https://github.com/skmendez/aiorcon
connections = []
id = 0
for server in tqdm(server_config):
    connections.append(RCONConnection())
    connections[-1].id = id
    connections[-1].loop = asyncio.get_event_loop()

    # initialize the RCON connection with ip, port, password and the event loop.
    connections[-1].rcon = connections[-1].loop.run_until_complete(
        aiorcon.RCON.create(server["ip"], server["port"],
                            server["rcon_pw"],
                            connections[-1].loop))
    id += 1

gameservers = []
for server in connections:
    gameservers.append({"id": server.id})

for i in range(0, len(teams)):
    teams[i]["id"] = i


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == 'kokoisapleb'


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


@app.route("/config/startTeamMatch", methods=["POST"])
def startTeamMatch():
    print(request.json)
    req = request.json

    req["team1"] = int(req["team1"])
    req["team2"] = int(req["team2"])

    team1 = {"name": teams[req["team1"]]["name"], "tag": teams[req["team1"]]["tag"],
             "players": teams[req["team1"]]["players"]}
    team2 = {"name": teams[req["team2"]]["name"], "tag": teams[req["team2"]]["tag"],
             "players": teams[req["team2"]]["players"]}

    matchname = f"{teams[req['team1']]['name']} vs {teams[req['team2']]['name']}"
    mapnumbers = int(req["mapnumbers"])
    matchcfg = render_template("match.cfg", team1=team1, team2=team2, serverid=req["server"],
                               matchname=matchname, mapnumbers=mapnumbers)

    logging.debug(matchcfg)
    os.makedirs("match_config", exist_ok=True)
    filename = os.path.join("match_config", str(time.time()).replace(".", "_") + ".cfg")
    with open(filename, "w") as matchfile:
        matchfile.write(matchcfg)

    server_conf = server_config[int(req["server"])]
    logging.debug(server_conf)
    os.system(
        f"scp -P {server_conf['ssh_port']} {filename} {server_conf['ssh_user']}@{server_conf['ip']}:{server_conf['ssh_path_to_conf_folder']}")

    connection = connections[int(req["server"])]
    loadmatch_res = connection.loop.run_until_complete(connection.rcon(f"get5_loadmatch {filename}"))
    logging.debug(loadmatch_res)

    logging.info(f"Created an loaded match {matchname}")

    return "{'status': 'ok'}"


@app.route("/config/startPlayerMatch", methods=["POST"])
def startPlayerMatch():
    print(request.json)
    req = request.json

    team1_players = [players[int(req["team1_player1"])],
                     players[int(req["team1_player2"])],
                     players[int(req["team1_player3"])],
                     players[int(req["team1_player4"])],
                     players[int(req["team1_player5"])]]

    team1 = {"name": req["team1"], "tag": req["team1"],
             "players": team1_players}

    team2_players = [players[int(req["team2_player1"])],
                     players[int(req["team2_player2"])],
                     players[int(req["team2_player3"])],
                     players[int(req["team2_player4"])],
                     players[int(req["team2_player5"])]]

    team2 = {"name": req["team2"], "tag": req["team2"],
             "players": team2_players}

    matchname = f"{team1['name']} vs {team2['name']}"
    mapnumbers = int(req["mapnumbers"])
    matchcfg = render_template("match.cfg", team1=team1, team2=team2, serverid=req["server"],
                               matchname=matchname, mapnumbers=mapnumbers)

    logging.debug(matchcfg)
    os.makedirs("match_config", exist_ok=True)
    filename = os.path.join("match_config", str(time.time()).replace(".", "_") + ".cfg")
    with open(filename, "w") as matchfile:
        matchfile.write(matchcfg)

    server_conf = server_config[int(req["server"])]
    logging.debug(server_conf)
    os.system(
        f"scp -P {server_conf['ssh_port']} {filename} {server_conf['ssh_user']}@{server_conf['ip']}:{server_conf['ssh_path_to_conf_folder']}")

    connection = connections[int(req["server"])]
    loadmatch_res = connection.loop.run_until_complete(connection.rcon(f"get5_loadmatch {filename}"))
    logging.debug(loadmatch_res)

    logging.info(f"Created an loaded match {matchname}")

    return "{'status': 'ok'}"


@app.route("/config/endMatch", methods=["POST"])
def endMatch():
    print(request.json)
    req = request.json

    connection = connections[int(req["server"])]

    endmatch_res = connection.loop.run_until_complete(connection.rcon(f"get5_endmatch"))
    logging.debug(endmatch_res)
    kickall_res = connection.loop.run_until_complete(connection.rcon(f"sm_kick @all Match was ended by an admin"))
    logging.debug(kickall_res)

    return ""


@app.route("/")
@cache.cached(timeout=0)
def index():
    return redirect("/status")


@app.route('/status')
@cache.cached(timeout=0)
def status():
    return render_template("status.html", gameserver=gameservers, ableToEndMatch=False)


@app.route('/adminStatus')
@requires_auth
@cache.cached(timeout=0)
def adminStatus():
    return render_template("status.html", gameserver=gameservers, ableToEndMatch=True)


@app.route('/config')
@requires_auth
@cache.cached(timeout=0)
def config():
    return render_template("config.html", gameserver=gameservers, teams=teams, players=players)


@app.route('/status/info')
# it is important that this is cached and
# essentially only executed every x seconds instead of every second by every client
@cache.cached(timeout=5)
def info():
    status = []

    for connection in connections:
        # need to parse values: CPU   NetIn   NetOut    Uptime  Maps   FPS   Players  Svms    +-ms   ~tick
        stats = connection.loop.run_until_complete(connection.rcon("stats"))

        # because get5 is awesome they already return json
        get5_stats = json.loads(connection.loop.run_until_complete(connection.rcon("get5_status")))
        status.append(
            {"id": connection.id, "ip": server_config[connection.id]["ip"] + ":" + str(server_config[connection.id]["port"]), "get5_stats": get5_stats, "stats": [float(value) for value in stats.split("\n")[1].split(" ") if value != '']})

    print(status)

    return json.dumps(status)


@app.errorhandler(401)
def error401(err):
    logging.error(f"401 error -> {err}")
    return render_template("401.html"), 401


@app.errorhandler(404)
def error404(err):
    logging.error(f"404 error -> {err} caused by {request.url}")
    return render_template("404.html"), 404


@app.errorhandler(500)
def error500(err):
    logging.error(f"500 error -> {err}")
    return render_template("500.html"), 500


if __name__ == '__main__':
    app.run(os.getenv("SERVER"))
