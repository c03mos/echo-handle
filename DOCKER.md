# Docker Deployment

## Files
- `Dockerfile`: builds the `handle` image
- `docker-compose.yml`: local container orchestration
- `.env.docker`: container-specific environment variables

## Shared storage requirement
`Data` must be shared with `arrangement`.

Reason:
- `handle` writes downloaded videos, extracted audio, accompaniment audio, and HLS output into the data directory
- `arrangement` needs to read these artifacts for task orchestration, metadata binding, and follow-up processing

Therefore, in Docker deployment:
- the host `Data` directory should be mounted into `handle`
- the same host `Data` directory should also be mounted into `arrangement`

## Mounted paths
The compose file mounts host directories into the container:
- `../Data` -> `/app/data`
- `../echo_data` -> `/app/echo_data`
- `../modelZoo` -> `/app/models`

## Build and run
```powershell
docker compose build
docker compose up -d
```

## Service address
After startup, the service is available at:
- `http://127.0.0.1:8000`

If other devices or `arrangement` need to access `/static/...` URLs, the service must listen on `0.0.0.0`, not only `127.0.0.1`.

Recommended local non-Docker startup:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_handle_lan.ps1
```

## Runtime notes
- HLS output is served from `/app/data` and exposed via `/static`
- SQLite task records are stored in `/app/echo_data/handle.db`
- `Kim_Vocal_2.onnx` is expected at `/app/models/Kim_Vocal_2/Kim_Vocal_2.onnx`

## Production notes
- Replace `PUBLIC_BASE_URL` in `.env.docker` with the actual gateway or host address
- If arrangement runs in another container, it should mount the same host `Data` directory
- For public deployment, put a reverse proxy in front of `handle`
