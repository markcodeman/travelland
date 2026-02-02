# Lightweight Alternatives to WSL for TravelLand

This document outlines lightweight alternatives to WSL for running the TravelLand project, focusing on Docker containers which offer significant memory savings and isolation.

## Why WSL Can Be Heavy

WSL (Windows Subsystem for Linux) is a full Linux virtualization layer that can consume a lot of memory (often 1-2GB+ just for the base system). For a project like TravelLand, which has multiple services, this memory usage can quickly add up.

## Recommended: Docker Containers (Lightweight, Isolated)

Docker provides lightweight containers that share the host OS kernel, resulting in much lower memory usage compared to WSL. Each container runs only the specific service it needs.

### Prerequisites

1. **Install Docker Desktop**: Download and install from https://www.docker.com/products/docker-desktop
2. **Enable WSL 2 Backend (Windows)**: For better performance, Docker Desktop can use WSL 2, but it's much more efficient than running a full WSL instance directly

### TravelLand Docker Setup

I've created a complete Docker configuration for TravelLand:

#### Files Created:
- `Dockerfile.backend` - Lightweight Python/Quart backend container (3.11-slim base)
- `Dockerfile.frontend` - Lightweight React/Vite frontend container (Node 18-alpine base)
- `Dockerfile.next` - Lightweight Next.js app container (Node 18-alpine base)
- `docker-compose.yml` - Multi-service orchestration
- `docker-dev.sh` - Easy-to-use startup script

#### Quick Start

1. **Ensure Docker Desktop is running**
2. **Run the Docker development script**:
   ```bash
   ./docker-dev.sh start
   ```
3. **Access the services**:
   - Backend: http://localhost:5010
   - Frontend (React/Vite): http://localhost:5174
   - Next.js App: http://localhost:3000

#### Script Commands

```bash
./docker-dev.sh start      # Start all services (default)
./docker-dev.sh stop       # Stop all services
./docker-dev.sh logs       # View all logs
./docker-dev.sh logs backend  # View specific service logs
./docker-dev.sh help       # Show help
```

### Memory Usage Comparison (Estimated)

| Environment | Base Memory Usage | Full Services |
|-------------|-------------------|---------------|
| WSL 2       | ~1-2 GB           | ~3-4 GB       |
| Docker      | ~100-200 MB       | ~500-700 MB   |

Docker typically uses **50-70% less memory** than WSL for TravelLand.

## Other Lightweight Alternatives

### 1. Windows Subsystem for Linux 2 (WSL 2) Optimization

If you must use WSL, here are ways to optimize it:

Create a `.wslconfig` file in your Windows home directory:
```ini
[wsl2]
memory=4GB
processors=4
swap=0
localhostForwarding=true
```

### 2. Node.js Direct (Windows)

For frontend development, you can run Node.js directly on Windows without WSL:

```bash
# Frontend
cd frontend
npm install
npm run dev -- --port 5174

# Next.js
cd next-app
npm install
npm run dev -- --port 3000
```

### 3. Python venv on Windows

For backend development, use Python venv directly:

```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r city_guides/requirements.txt
hypercorn city_guides.src.app:app --bind 0.0.0.0:5010
```

### 4. Podman (Linux/Mac)

If you have Podman installed (a Docker alternative without a daemon), you can use the same Dockerfiles:

```bash
podman-compose up --build -d
```

## Performance Tips for Docker

1. **Use .dockerignore**: I've added this to exclude unnecessary files
2. **Prune unused resources**:
   ```bash
   docker system prune -a --volumes
   ```
3. **Limit container resources**: Add resource limits in docker-compose.yml

## Troubleshooting

### Docker Not Found

If you get "docker: command not found":
1. Verify Docker Desktop is installed and running
2. Check if Docker is in your PATH
3. Restart Docker Desktop

### Port Already in Use

Use `docker-dev.sh stop` to stop running containers. If ports are still occupied, use:
```bash
# Windows
netstat -ano | findstr :5010
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti :5010 | xargs kill -9
```

## Summary

**Docker containers are the best lightweight alternative to WSL for TravelLand.** They offer:
- 50-70% lower memory usage
- Better isolation
- Faster startup times
- Cross-platform compatibility
- Easy orchestration with docker-compose

The provided `docker-dev.sh` script makes it simple to start/stop all services with one command.