# Containerized FastAPI Inference Service

A small prediction API built with FastAPI and packaged as a production-grade Docker image. The model itself is intentionally simple (it just doubles the input) - the point of this project is the containerization, not the math. The request/response shape is the same one real model servers use, so swapping in an actual ML model later doesn't change anything else.

Built by **Manish Kumar** - [LinkedIn](https://www.linkedin.com/in/manishsinghkuswaha/)

## Why this exists

Every developer has hit the "works on my machine" problem: the app runs fine locally, then breaks on the server because of a different Python version or a missing library.

This project packages the app together with its entire environment into a single versioned image. Build it once, run it anywhere - laptop, EC2, Kubernetes - and it behaves exactly the same.

## What's in here

```
inference-service/
├── app.py              # the API (two endpoints: /predict and /health)
├── requirements.txt    # pinned dependencies
├── .dockerignore       # keeps junk and secrets out of the image
├── Dockerfile          # the build recipe
└── README.md
```

Stack: FastAPI (the API framework), Uvicorn (the server that runs it), Docker.

## Setup

You need the Docker CLI and a running daemon. Docker Desktop works fine. If you can't install it (license reasons etc.), Colima does the same job on macOS:

```bash
brew install colima docker
colima start
docker run hello-world    # sanity check
```

Two Colima gotchas I ran into myself:
- `docker not found` when starting colima - the CLI is a separate install, run `brew install docker`
- `docker-credential-osxkeychain not found` on first pull - leftover Docker Desktop config. Fix: `echo '{}' > ~/.docker/config.json`

## Running it

```bash
docker build -t inference:1.0 .
docker run -d -p 8000:8000 --name inference inference:1.0

curl "http://localhost:8000/predict?x=21"
# {"prediction": 42.0}
```

FastAPI also generates interactive docs automatically - open http://localhost:8000/docs in a browser and you can test the endpoints from there.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/predict?x=<number>` | returns `{"prediction": x*2}` |
| GET | `/health` | returns `{"status": "ok"}` - used by the Docker healthcheck |
| GET | `/docs` | Swagger UI |

## Design notes

A few deliberate choices in the Dockerfile, and what each one prevents:

- **`python:3.12-slim` base, everything pinned** - reproducible builds; the same Dockerfile produces the same image in six months
- **requirements.txt copied and installed before the code** - code edits don't invalidate the pip layer, so rebuilds take ~2 seconds instead of minutes
- **runs as a non-root user (`appuser`)** - a container escape as root would mean root on the host
- **`/health` endpoint wired to a Docker HEALTHCHECK** - "the process is running" is not the same as "the app is answering"; this lets Docker and orchestrators tell the difference
- **`--host 0.0.0.0` in the CMD** - binding to 127.0.0.1 inside a container makes it unreachable through port mapping. Classic mistake, designed out
- **`.dockerignore` excludes `.env`, `.git`, `venv/`** - image layers are permanent; a secret copied in once is extractable forever, even if a later layer deletes the file

## Checking that it all works

Each design decision can be verified with a command:

```bash
curl "http://localhost:8000/predict?x=21"   # the API works
docker ps                                   # STATUS shows (healthy) after ~30s
docker exec -it inference whoami            # appuser, not root
docker logs inference                       # request log
```

## Publishing

```bash
docker login
docker tag inference:1.0 YOUR_USER/inference:1.0
docker push YOUR_USER/inference:1.0
```

Don't deploy `:latest` in production - pin a version tag, and ideally add the git SHA so you always know exactly what's running.

## Troubleshooting

- **curl hangs from outside but works via `docker exec`** - the app is bound to 127.0.0.1; the CMD needs `--host 0.0.0.0`
- **port is already allocated** - something else is on 8000, use `-p 8001:8000`
- **STATUS shows (unhealthy)** - check `docker logs inference` and hit /health from inside via exec
- **Cannot connect to the Docker daemon** - the engine isn't running; start Docker Desktop or `colima start`

## Cleanup

```bash
docker stop inference && docker rm inference
```

## Ideas for extending it

- convert to a multi-stage build and compare image sizes
- scan the image with Trivy and fix anything HIGH/CRITICAL
- add a GitHub Actions workflow that builds and pushes on every commit, tagged with the git SHA
- replace `x * 2` with a real scikit-learn model - the container setup barely changes, which is the whole point

---

**Manish Kumar** - DevOps mentor
[linkedin.com/in/manishsinghkuswaha](https://www.linkedin.com/in/manishsinghkuswaha/)
