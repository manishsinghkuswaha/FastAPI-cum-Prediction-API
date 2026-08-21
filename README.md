# Docker Networking Demo - API + Database on a Custom Network

Two containers talking to each other by name: a FastAPI prediction service and a PostgreSQL database, connected over a user-defined Docker network. Every prediction the API makes is stored in the database and can be read back through a `/history` endpoint.

This is the follow-up to the single-container inference project. That one taught you how to build and ship an image. This one teaches what real applications need next: containers working together.

Built by **Manish Kumar** - [LinkedIn](https://www.linkedin.com/in/manishsinghkuswaha/)

## What this demonstrates

- Why `localhost` does not work between containers (each container is its own isolated box)
- Custom (user-defined) bridge networks and the built-in DNS that comes with them
- Containers reaching each other by container NAME instead of fragile IPs
- Passing configuration through environment variables instead of hardcoding
- Why the database gets no published port - and why that makes it safer
- Network isolation: containers outside the network cannot even resolve the name

## Project structure

```
network-demo/
├── app.py              # FastAPI service: /predict, /history, /health
├── requirements.txt    # fastapi, uvicorn, psycopg2-binary (all pinned)
├── Dockerfile          # same production pattern as the inference project
└── README.md
```

The interesting line in `app.py` is this one:

```python
DB_HOST = os.getenv("DB_HOST", "localhost")
```

The code never knows where the database is. It reads the address from an environment variable, and we pass the container name (`db`) at run time. Docker's DNS does the rest. This is the standard pattern for configuring containers.

There is also a retry loop on startup - the API tries to reach the database up to 10 times before giving up. Containers start in whatever order they want, so real apps must tolerate a dependency that is not ready yet.

## Prerequisites

Docker CLI + a running daemon (Docker Desktop or Colima). Pull the Postgres image before class/demo if your internet is slow: `docker pull postgres:16` (~140 MB).

## Step-by-step walkthrough

Run these in order. Each step explains what the command does and why you see the output you see.

### Step 1 - Build the API image

```bash
docker build -t predict-api:1.0 .
```

**What it does:** reads the Dockerfile and builds an image, tagging it `predict-api:1.0`.

**Why the output looks like that:** you'll see one step per Dockerfile instruction - each becomes a layer. The pip install step takes the longest because it downloads fastapi, uvicorn and the Postgres driver. If you rebuild without changes, every step says `CACHED` and finishes in about a second - that's the layer cache.

### Step 2 - Create the network

```bash
docker network create app-net
```

**What it does:** creates a user-defined bridge network - a private "hallway" that containers can be plugged into.

**Why we need it:** the default bridge network has no DNS, so containers there can only reach each other by IP - and container IPs change on every restart. A custom network gives us name-based lookup for free.

**Why the output looks like that:** Docker prints a long hex string. That's just the network's ID. Run `docker network ls` and you'll see `app-net` listed next to the default `bridge`.

### Step 3 - Start the database on the network

```bash
docker run -d --name db --network app-net \
  -e POSTGRES_PASSWORD=secret123 postgres:16
```

**What it does:** starts Postgres in the background (`-d`), names the container `db`, plugs it into `app-net`, and sets the password Postgres requires via an environment variable (`-e`).

**Two things to notice:**
- The name `db` is not decoration - on a custom network, the container name becomes its hostname. Every container on `app-net` can now reach this database at the address `db`.
- There is deliberately NO `-p` flag. The database never talks to the outside world, only to the API - and the API is inside the network. A port that is not published cannot be scanned or attacked. Publish ports only for the service that actually faces users.

**Why the output looks like that:** again just a container ID. `docker ps` shows the container with no entry under PORTS mapped to the host - that's the "no front door" proof.

### Step 4 - Start the API on the same network

```bash
docker run -d --name api --network app-net -p 8000:8000 \
  -e DB_HOST=db predict-api:1.0
```

**What it does:** starts our API, plugs it into the same network, publishes port 8000 (this one DOES face users, so it gets a door), and passes `DB_HOST=db` - literally telling the app "your database is at the address db".

**Why this is the key command of the demo:** look at what we passed as the database address. Not an IP. Not localhost. The other container's NAME. The app code reads it from the environment and connects to it like any hostname.

### Step 5 - The proof: read the API's logs

```bash
docker logs api
```

**What it does:** prints everything the API container has written to its output.

**Why the output looks like that:** you'll see either `connected to db at host 'db' - table ready` straight away, or one or two `db not ready (attempt 1/10)` lines first and then the success line. The retries happen because Postgres takes a few seconds to initialize on first start - the API patiently retries until the database answers. That's the startup race, handled. The success line is Docker DNS working: the name `db` was resolved to the database container and a real TCP connection was made.

### Step 6 - Make predictions

```bash
curl "http://localhost:8000/predict?x=21"
curl "http://localhost:8000/predict?x=50"
```

**What it does:** calls the API from your machine, through the published port.

**Why the output looks like that:** you get `{"prediction": 42.0, "saved": true}`. The `saved: true` is the interesting part - before answering you, the API wrote a row into Postgres. That request travelled: your terminal -> host port 8000 -> api container -> app-net -> db container, and back.

### Step 7 - Read the history back

```bash
curl "http://localhost:8000/history"
```

**What it does:** asks the API for the last 10 predictions - which it fetches from the database.

**Why the output looks like that:** you see the predictions you just made, with timestamps, newest first. This is the round-trip proof: the data physically lives in one container and is being served by another, across the network.

### Step 8 - The negative proof: off the network, the name doesn't exist

```bash
docker run --rm postgres:16 psql -h db -U postgres
```

**What it does:** starts a throwaway Postgres client container (`--rm` deletes it when it exits) and tells it to connect to the host `db`. Note what's missing: no `--network app-net`.

**Why the output looks like that:** it fails with `could not translate host name "db"`. This container landed on the default bridge - a different hallway. From there, the name `db` simply does not resolve. This failure is the isolation feature working: your database is invisible to anything you didn't explicitly put on its network.

Now run the same command WITH the network and watch it succeed:

```bash
docker run -it --rm --network app-net postgres:16 psql -h db -U postgres
# password: secret123 -> you get a postgres=# prompt
```

Same command, one flag difference, opposite result. That flag is the whole lesson.

### Step 9 - Cleanup

```bash
docker rm -f api db
docker network rm app-net
```

**What it does:** force-removes both containers (`-f` = stop and remove in one go), then removes the network. Networks can only be deleted once nothing is attached to them, which is why the containers go first.

**One thing worth trying before you clean up:** delete just the db container and recreate it, then check `/history` - the predictions are gone. Container filesystems die with the container. That problem (and its fix, volumes) is the next lesson.

## Troubleshooting

- **`docker logs api` shows all 10 retries then a crash** - the db container isn't on the same network, or isn't running. Check `docker ps` and that both used `--network app-net`.
- **`curl localhost:8000` connection refused** - the API container exited (check `docker ps -a` and `docker logs api`) or you forgot `-p 8000:8000`.
- **`port is already allocated`** - something else owns 8000; use `-p 8001:8000` and curl `:8001`.
- **`could not translate host name "db"` from the API itself** - you're on the DEFAULT bridge (no DNS there). Both containers need the custom network.

## The takeaway

Create a network, name your containers meaningfully, let them find each other by name, and publish a port only for the service that faces the outside. That is the pattern behind every multi-container app - and it's exactly what Docker Compose automates in the next lesson.

---

**Manish Kumar** - DevOps mentor
[linkedin.com/in/manishsinghkuswaha](https://www.linkedin.com/in/manishsinghkuswaha/)
