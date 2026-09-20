# Day 001 — Containerizing an Angular SPA

Taking the HRMS frontend from a manual, by-hand server deployment to a reproducible Docker image served by nginx.

![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-009639?style=flat-square&logo=nginx&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-DD0031?style=flat-square&logo=angular&logoColor=white)

---

## The problem

Deploying the HRMS frontend meant SSHing into the server and running roughly fifteen commands by hand:

```bash
apt update && apt upgrade -y
apt install nodejs npm nginx -y
systemctl enable --now nginx

cd /path/to/frontend
npm install
npm run build

sudo mkdir -p /var/www/hrms
sudo cp -r dist/hrms/browser/* /var/www/hrms/

sudo cp nginx.conf /etc/nginx/sites-available/hrms
sudo ln -s /etc/nginx/sites-available/hrms /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

This works, but it has real problems:

- **Not reproducible.** The build depends on whichever Node version the server happens to have. A machine set up six months apart gets a different one.
- **Server drift.** Every manual fix makes the server a little more unique and a little harder to rebuild.
- **Node in production.** The server needs a full Node and npm toolchain permanently installed, just to produce static files once.
- **Error-prone.** Fifteen ordered commands, run from memory, at 8pm.

## The goal

One command to build and deploy. No Node on the server. Identical result on every machine.

---

## What was built

```
Day-001-Practice/
├── Dockerfile              # multi-stage: build with Node, serve with nginx
├── docker-compose.yml      # service definition, ports, restart policy
├── nginx.conf              # SPA routing, caching, compression
├── .dockerignore           # keeps local junk out of the build context
└── README.md
```

### Dockerfile

```dockerfile
# syntax=docker/dockerfile:1

# ---------- Stage 1: build ----------
FROM node:22-bookworm-slim AS build

WORKDIR /app

# Manifests first — this layer stays cached until dependencies change
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- Stage 2: serve ----------
FROM nginx:1.27-alpine

RUN rm -rf /usr/share/nginx/html/*

# Only the compiled output crosses the stage boundary
COPY --from=build /app/dist/hrms/browser/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

The two-stage split is the central idea. Node, npm, and the entire `node_modules` tree exist only in stage one. Stage two starts from a clean nginx image and copies in nothing but the compiled `dist/` output.

### nginx.conf

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback — see "Lessons" below
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Angular fingerprints filenames (main-A1B2C3.js), so cache them hard
    location ~* \.(?:js|css|woff2?|png|jpe?g|gif|svg|ico)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # index.html is NOT fingerprinted — never cache it
    location = /index.html {
        add_header Cache-Control "no-store";
    }

    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options        "SAMEORIGIN" always;
    add_header Referrer-Policy        "strict-origin-when-cross-origin" always;
}
```

### docker-compose.yml

```yaml
services:
  hrms-frontend:
    build:
      context: .
      dockerfile: Dockerfile
    image: hrms-frontend:latest
    container_name: hrms-frontend
    ports:
      - "9090:80"
    restart: unless-stopped
    networks:
      - backend
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost/"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

networks:
  backend:
    driver: bridge
```

---

## Running it

```bash
docker compose up -d --build
```

Open **http://localhost:9090**

```bash
docker compose ps          # container state and health
docker compose logs -f     # follow nginx access and error logs
docker compose down        # stop and remove
```

Redeploying after a code change is the same single command — Compose rebuilds the image and swaps the container.

---

## Lessons learned

The first attempt at this had five real bugs. Each one is worth keeping.

### 1. `RUN cd` does nothing

```dockerfile
RUN cd /app/repo        # ✗ silently useless
RUN npm install         # runs in the previous working directory
```

Every `RUN` spawns a fresh shell. The `cd` applies inside that shell and is discarded when it exits. `WORKDIR` is the directive that actually persists across layers.

```dockerfile
WORKDIR /app/repo       # ✓ applies to every following instruction
```

### 2. A volume over the web root freezes the deploy

```yaml
volumes:
  - valum:/usr/share/nginx/html    # ✗
```

This is the subtle one. Docker will not overwrite a named volume that already contains data. The first `up` populates the volume from the image; from then on, every rebuild produces a fresh image that the container **ignores**, because the stale volume is mounted on top.

The symptom is maddening — the build succeeds, the container restarts, and the old version is still served. Static assets baked into an image should never have a volume mounted over them. Volumes are for data that must survive the container, not for content shipped inside it.

### 3. `apt upgrade` makes builds non-reproducible

```dockerfile
RUN apt update && apt upgrade -y    # ✗
```

The same Dockerfile now produces a different image every week, depending on what upstream published. That defeats the point of building an image at all. Pin the base image tag (`nginx:1.27-alpine`) and let a deliberate tag bump be the thing that changes versions.

Related: without `rm -rf /var/lib/apt/lists/*`, the package index is baked into the layer permanently — deleting it in a later `RUN` doesn't shrink the image, because layers are additive.

### 4. `npm install` vs `npm ci`

`npm install` can resolve to newer versions than `package-lock.json` specifies, so the build server can quietly produce a different dependency tree than the machine it was tested on. `npm ci` installs the lock file exactly, fails loudly if the lock is out of sync, and is faster because it skips resolution.

### 5. Layer order controls cache hits

```dockerfile
COPY package.json package-lock.json ./   # changes rarely
RUN npm ci                                # expensive — stays cached
COPY . .                                  # changes constantly
RUN npm run build
```

Copy the manifests, install, *then* copy the source. Reverse the order and every one-line source edit invalidates the `npm ci` layer, turning a 30-second rebuild into a three-minute one.

And without a `.dockerignore`, `COPY . .` drags the local `node_modules`, `.git`, and `.angular` cache into the build context — slow, and it can conflict with what `npm ci` installs.

### 6. Why the SPA needs `try_files`

An Angular route like `/employees/42` has no corresponding file on disk. Loading it via in-app navigation works, because the router handles it client-side. Typing it in the address bar or hitting refresh sends a real HTTP request, nginx looks for a file that doesn't exist, and returns 404.

```nginx
try_files $uri $uri/ /index.html;
```

Try the literal file, then the directory, then fall back to `index.html` so the router can take over. This one line is the most common missing piece in SPA deployments.

---

## Result

| | Manual | Containerized |
|---|---|---|
| Commands to deploy | ~15 | 1 |
| Node on the production host | required | not installed |
| Reproducible across machines | no | yes |
| Rollback | rebuild and hope | `docker run` the previous image tag |
| Runtime image size | n/a (full host) | ~50 MB |

---

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| 404 on refresh at a sub-route | `try_files` missing, or `nginx.conf` not copied into the image |
| Old version served after rebuild | Volume mounted over the web root, or browser cache — hard-refresh first |
| `npm ci` fails during build | `package-lock.json` missing or out of sync with `package.json` |
| Build killed / out of memory | Add `ENV NODE_OPTIONS=--max-old-space-size=4096` to the build stage |
| Port already allocated | `sudo ss -lntp \| grep 9090` |

Inspect what actually landed in the image:

```bash
docker compose exec hrms-frontend ls -la /usr/share/nginx/html
docker compose exec hrms-frontend cat /etc/nginx/conf.d/default.conf
docker compose exec hrms-frontend nginx -t
```

---

## Notes

- The build copies from `dist/hrms/browser/`, the Angular 17+ output layout. Angular 16 and earlier write to `dist/<project>/` with no `browser/` subfolder.
- For production, put a TLS-terminating reverse proxy in front and bind the container to loopback (`"127.0.0.1:9090:80"`) so the port isn't exposed directly.
- If the frontend calls an API, proxy it through this nginx via a `location /api/` block rather than pointing the browser at a second origin — same origin, no CORS.

## Next

Build this image in CI and push it to GHCR, so the server pulls a tagged artifact instead of compiling Angular on production hardware.
