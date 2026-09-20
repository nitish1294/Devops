# HRMS Frontend

Angular single-page application for the HRMS portal, packaged as a Docker image and served by nginx.

The image is built in two stages: Node compiles the app, then only the compiled static files are copied into a small nginx image. The runtime image contains no Node, no npm, and no source code.

---

## Requirements

| Tool | Version |
|---|---|
| Docker Engine | 24+ |
| Docker Compose | v2 (`docker compose`, not `docker-compose`) |
| Node.js (local dev only) | 22.x |

Nothing else needs to be installed on the host. Node and nginx both live inside the image.

---

## Repository layout

```
.
├── src/                    # Angular source
├── angular.json
├── package.json
├── package-lock.json       # required — the build uses `npm ci`
├── Dockerfile              # multi-stage build
├── docker-compose.yml
├── nginx.conf              # server block, copied to conf.d/default.conf
├── .dockerignore
└── README.md
```

---

## Quick start

```bash
git clone https://github.com/<your-username>/hrms-frontend.git
cd hrms-frontend

docker compose up -d --build
```

The app is then available at **http://localhost:9090**

Check it came up cleanly:

```bash
docker compose ps
docker compose logs -f hrms-frontend
```

Stop it:

```bash
docker compose down
```

---

## Without Compose

```bash
docker build -t hrms-frontend:latest .

docker run -d \
  --name hrms-frontend \
  -p 9090:80 \
  --restart unless-stopped \
  hrms-frontend:latest
```

---

## Deploying a new version

```bash
git pull
docker compose up -d --build
```

Compose rebuilds the image and swaps the container. Because the static files are baked into the image and no volume is mounted over the web root, the new build is served immediately.

Clean up old dangling images now and then:

```bash
docker image prune -f
```

---

## Configuration

### Changing the published port

Edit the left-hand side of the port mapping in `docker-compose.yml`. The container always listens on 80 internally.

```yaml
ports:
  - "8080:80"     # host 8080 → container 80
```

### Pointing the frontend at a backend API

Uncomment the `location /api/` block in `nginx.conf` and set `proxy_pass` to your API service. If the backend runs as another container, put it on the same `backend` network and reference it by its service name:

```nginx
location /api/ {
    proxy_pass http://hrms-backend:8080/;
    ...
}
```

Then rebuild. Proxying through nginx means the browser only ever talks to one origin, which sidesteps CORS entirely.

### Build output path

The Dockerfile copies from `dist/hrms/browser/`. If your `angular.json` uses a different `outputPath` or project name, update this line:

```dockerfile
COPY --from=build /app/dist/hrms/browser/ /usr/share/nginx/html/
```

Angular 16 and earlier put files directly in `dist/<project>/` with no `browser/` subfolder.

---

## Local development

```bash
npm install
npm start          # http://localhost:4200 with live reload
```

Use `ng serve` for day-to-day work. The Docker image is for staging and production — rebuilding it on every code change is far slower than the dev server.

---

## Running behind a reverse proxy

In production this container normally sits behind a host-level nginx or a load balancer that terminates TLS:

```nginx
server {
    listen 443 ssl http2;
    server_name hrms.example.com;

    ssl_certificate     /etc/letsencrypt/live/hrms.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hrms.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:9090;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

Bind the container to loopback only (`"127.0.0.1:9090:80"`) so port 9090 isn't reachable from outside the host.

---

## Troubleshooting

**Refreshing on a sub-route gives 404**
The `try_files $uri $uri/ /index.html;` line is missing or `nginx.conf` wasn't copied. Confirm with:
```bash
docker compose exec hrms-frontend cat /etc/nginx/conf.d/default.conf
```

**Old version still showing after a rebuild**
First hard-refresh the browser (Ctrl+Shift+R). If it persists, check that no volume is mounted over `/usr/share/nginx/html` — Docker will not overwrite a volume that already has content:
```bash
docker compose exec hrms-frontend ls /usr/share/nginx/html
```

**`npm ci` fails during build**
`package-lock.json` is missing or out of sync with `package.json`. Run `npm install` locally and commit the updated lock file.

**Build runs out of memory**
Large Angular builds can exceed Node's default heap. Add to the build stage:
```dockerfile
ENV NODE_OPTIONS=--max-old-space-size=4096
```

**Port already in use**
```bash
sudo ss -lntp | grep 9090
```
Change the host port or stop whatever holds it.

---

## Appendix: the original manual deployment

Kept for reference. This is what the container now does automatically.

```bash
# Install runtime
apt update && apt upgrade -y
apt install nodejs npm nginx -y
systemctl enable nginx
systemctl start nginx

# Build the app
cd /path/to/frontend
npm install
npm run build

# Publish the static files
sudo mkdir -p /var/www/hrms
sudo cp -r dist/hrms/browser/* /var/www/hrms/

# Wire up the nginx site
sudo cp nginx.conf /etc/nginx/sites-available/hrms
sudo ln -s /etc/nginx/sites-available/hrms /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Note that with this route `root` in the server block must be `/var/www/hrms`, whereas the container uses nginx's default `/usr/share/nginx/html`.

The container approach replaces all of the above with one command, builds identically on every machine, and leaves the host with nothing installed but Docker.
