<h1 align="center">DevOps Practice</h1>

<p align="center">
  A day-by-day log of hands-on DevOps work — containers, web servers, CI/CD, and infrastructure.<br>
  Each folder is one self-contained exercise, built from scratch and documented.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Nginx-009639?style=flat-square&logo=nginx&logoColor=white" alt="Nginx">
  <img src="https://img.shields.io/badge/Angular-DD0031?style=flat-square&logo=angular&logoColor=white" alt="Angular">
  <img src="https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black" alt="Linux">
  <img src="https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white" alt="Git">
</p>

<p align="center">
  <img src="https://img.shields.io/github/last-commit/nitish1294/Devops?style=flat-square&color=blue" alt="Last commit">
  <img src="https://img.shields.io/github/repo-size/nitish1294/Devops?style=flat-square&color=green" alt="Repo size">
  <img src="https://img.shields.io/github/languages/top/nitish1294/Devops?style=flat-square" alt="Top language">
</p>

---

## About

This repository tracks my practical DevOps learning. Rather than following tutorials passively, each exercise takes something I already deploy manually and rebuilds it properly — containerized, reproducible, and documented.

Every day folder answers three questions:

- **What was the problem?** The manual or fragile process being replaced.
- **What was built?** The working configuration, with all files committed.
- **What was learned?** The mistakes made along the way, and why the fix works.

The last part matters most. Working config is easy to copy; understanding why it works is the actual output.

---

## Practice log

| Day | Topic | Focus | Status |
|:---:|-------|-------|:------:|
| [001](./Day-001-Practice) | Containerizing an Angular SPA | Multi-stage Dockerfile · nginx · Docker Compose | ✅ |
| 002 | *planned* | — | ⏳ |
| 003 | *planned* | — | ⏳ |

> Table updated as each day lands. Click a day to open its own README.

---

## Repository structure

```
Devops/
├── Day-001-Practice/          # Angular SPA → Docker + nginx
│   ├── README.md              # objective, walkthrough, lessons
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── .dockerignore
├── .gitignore
└── README.md                  # you are here
```

Each day folder is independent. Nothing outside it is required to run it.

---

## Getting started

```bash
git clone https://github.com/nitish1294/Devops.git
cd Devops
```

Then pick a day and follow its own README:

```bash
cd Day-001-Practice
cat README.md
```

Most exercises need only Docker installed. Any extra prerequisites are listed in the individual day's README.

---

## Tools and technologies

| Area | Tools |
|------|-------|
| Containers | Docker, Docker Compose, multi-stage builds |
| Web servers | nginx — reverse proxy, SPA routing, TLS termination |
| Frontend builds | Angular, Node.js, npm |
| Operating systems | Debian / Ubuntu, Alpine |
| Version control | Git, GitHub |
| Planned | GitHub Actions, Kubernetes, Prometheus, Grafana |

---

## Conventions

A few rules that keep the repo consistent as it grows:

- **Folder naming** — `Day-NNN-Practice`, zero-padded so they sort correctly.
- **One README per day** — objective, steps, and lessons learned. No day ships undocumented.
- **Runnable as committed** — if the config needs a secret or a local path, that's called out explicitly.
- **No secrets in Git** — `.env`, keys, and certificates stay out; the root `.gitignore` enforces this.
- **Commit messages** — present tense, scoped to the day: `Day-001: add multi-stage Dockerfile`.

---

## Roadmap

- [x] Containerize a frontend build with a multi-stage Dockerfile
- [ ] Add a CI pipeline that builds and pushes images to GHCR
- [ ] Container health checks and structured logging
- [ ] Reverse proxy with automated TLS (Caddy or nginx + Certbot)
- [ ] Multi-service stack: frontend, backend, database
- [ ] Deploy the same stack to Kubernetes
- [ ] Monitoring with Prometheus and Grafana

---

## Author

**Nitish Sharma** — [@nitish1294](https://github.com/nitish1294)

IT administrator working across Windows fleet management, Linux infrastructure, and full-stack deployment.

---

<p align="center">
  <sub>Suggestions and corrections welcome — open an issue.</sub>
</p>
