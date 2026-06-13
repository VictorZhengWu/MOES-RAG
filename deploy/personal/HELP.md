# Marine & Offshore Expert System — Help

## Getting Started

### Requirements

- **Docker Desktop** (free): [Download](https://www.docker.com/products/docker-desktop/)
- **RAM**: 8 GB minimum, 12 GB recommended
- **Disk**: 5 GB free space
- **OS**: Windows 10+, macOS 12+, or Linux

### Installation

1. Install Docker Desktop and restart your computer
2. Copy this entire folder to your computer
3. Start Docker Desktop and wait for the whale icon to stop animating
4. **Windows**: Double-click `start.bat`
   **Mac/Linux**: Run `./start.sh`

First run downloads Docker images (5-10 minutes). Subsequent starts take ~30 seconds.

### Access

| URL | Purpose |
|-----|---------|
| `http://localhost:3000` | User Portal |
| `http://localhost:8000/docs` | API Documentation |
| `http://localhost:3000/help` | Online Help |

## Common Issues

### "Docker is not running"

The Docker whale icon in the system tray should be stationary (not animating). If it's still animating, wait for it to finish initializing.

### "Port 8000 already in use"

Another program is using port 8000. Common causes: other web servers, Skype, IIS.
**Fix**: Stop the other program, or edit `docker-compose.yml` to change `8000:8000` to `8001:8000`.

### "Out of memory" or "Container exited"

Your computer doesn't have enough RAM. Try:
- Close other programs (browser, IDE, etc.)
- Increase Docker's memory limit: Docker Desktop → Settings → Resources → Memory

### "Cannot connect" or "Connection refused"

Services may still be starting. Wait 60 seconds and try again.

### Using document parsing

The document parsing engine (M1) is optional and disabled by default to save RAM.
To enable:
```
docker compose --profile parsing up -d
```
This requires **12+ GB RAM**. To disable later:
```
docker compose --profile parsing down
```

### Using local LLM (no internet needed)

To run offline with a local LLM via Ollama:
```
docker compose --profile llm up -d
docker exec -it marine-ollama ollama pull qwen2.5:7b
```
Then configure the LLM backend in Admin Portal → LLM Config:
- Provider: ollama
- Model: qwen2.5:7b
- Base URL: http://ollama:11434/v1

## Stopping

- **Windows**: Double-click `stop.bat`
- **Mac/Linux**: Run `docker compose down`

To completely remove all data (fresh start):
```
docker compose down -v
```

## Data Location

All data is stored in Docker volumes. To back up:
```
docker run --rm -v marine_data:/data -v %cd%/backup:/backup alpine cp -r /data /backup/
```

## Getting More Help

- Check online help: `http://localhost:3000/help`
- Review Docker logs: `docker compose logs m8`
- Restart fresh: `docker compose down -v && docker compose up -d`
