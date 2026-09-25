# Day 002 — Databases in Docker

Running PostgreSQL and MongoDB as containers, each built from its own Dockerfile and managed with its own Compose file.

![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white)

---

## Objective

Get both databases running in containers, confirm data survives a restart, and work with each from its shell — creating databases, inserting records, querying, and dropping them.

Two separate stacks rather than one combined file, so each can be started, inspected, and destroyed independently.

```
Day-002-Practice/
├── postgres/
│   ├── Dockerfile
│   └── docker-compose.yml
└── mongodb/
    ├── Dockerfile
    └── docker-compose.yml
```

---

## Part 1 — PostgreSQL

### Dockerfile

```dockerfile
FROM postgres:14.24-alpine3.23

ENV POSTGRES_USER=myuser
ENV POSTGRES_PASSWORD=mypassword
ENV POSTGRES_DB=mydb

VOLUME ["/var/lib/postgresql/data"]
```

The three `POSTGRES_*` variables are read by the image's entrypoint on first start. They create the role, set its password, and create an initial database owned by that role.

### docker-compose.yml

```yaml
services:
  postgresdb:
    build: .
    container_name: postgres-db
    ports:
      - "127.0.0.1:5432:5432"
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### Running it

```bash
cd postgres
docker compose up -d --build
docker compose ps
```

Connect:

```bash
docker compose exec postgresdb psql -U myuser -d mydb
```

### Session

```sql
mydb=# \l
                              List of databases
   Name    | Owner  | Encoding |  Collate   |   Ctype
-----------+--------+----------+------------+------------
 mydb      | myuser | UTF8     | en_US.utf8 | en_US.utf8
 postgres  | myuser | UTF8     | en_US.utf8 | en_US.utf8
 template0 | myuser | UTF8     | en_US.utf8 | en_US.utf8
 template1 | myuser | UTF8     | en_US.utf8 | en_US.utf8
(4 rows)

mydb=# CREATE DATABASE practical;
CREATE DATABASE

mydb=# \c practical
You are now connected to database "practical" as user "myuser".

practical=# CREATE TABLE employees (
practical(#     id SERIAL PRIMARY KEY,
practical(#     name VARCHAR(50) NOT NULL,
practical(#     department VARCHAR(50)
practical(# );
CREATE TABLE

practical=# INSERT INTO employees (name, department)
practical-# VALUES ('John Doe', 'Engineering');
INSERT 0 1

practical=# \dt
          List of relations
 Schema |   Name    | Type  | Owner
--------+-----------+-------+--------
 public | employees | table | myuser
(1 row)

practical=# SELECT * FROM employees;
 id |   name   | department
----+----------+-------------
  1 | John Doe | Engineering
(1 row)
```

Dropping it — note the reconnect:

```sql
practical=# \c postgres
You are now connected to database "postgres" as user "myuser".

postgres=# DROP DATABASE practical;
DROP DATABASE
```

A database cannot be dropped from a session connected to it. Switching to `postgres` first is what makes the drop succeed.

### Stopping

```bash
docker compose down        # stop, data kept in the pgdata volume
docker compose down -v     # stop and destroy the volume — no undo
```

---

## Part 2 — MongoDB

### Dockerfile

```dockerfile
FROM mongo:7.0

ENV MONGO_INITDB_ROOT_USERNAME=root
ENV MONGO_INITDB_ROOT_PASSWORD=password

VOLUME ["/data/db"]
```

Mongo enables authentication only when **both** variables are set, and only when `/data/db` is empty on first start.

### docker-compose.yml

```yaml
services:
  mongodb:
    build: .
    container_name: mongodb
    ports:
      - "127.0.0.1:27017:27017"
    restart: unless-stopped
    volumes:
      - mongodata:/data/db

volumes:
  mongodata:
```

### Running it

```bash
cd mongodb
docker compose up -d --build
docker compose ps
```

Connect:

```bash
docker compose exec mongodb mongosh -u root -p password --authenticationDatabase admin
```

`--authenticationDatabase admin` is required. The root user is created in `admin`, not in the application database.

### Verify authentication is on

```bash
docker compose exec mongodb mongosh --quiet --eval "db.adminCommand({listDatabases:1})"
```

The correct result is an error: `command listDatabases requires authentication`. If it prints a database list instead, auth is off — see [Lesson 1](#1-env-key-value-silently-disabled-authentication).

### Session

```javascript
> show dbs
admin    100.00 KiB
config    12.00 KiB
local     72.00 KiB

> use myappdb
switched to db myappdb

> db.users.insertMany([
    { name: "Nitish", email: "nitish@example.com", age: 28 },
    { name: "John",   email: "john@example.com",   age: 25 },
    { name: "Alice",  email: "alice@example.com",  age: 30 }
  ])

> show collections
users

> db.users.find().pretty()

> db.users.countDocuments()
3

> db.users.findOne({ name: "Nitish" })

> db.users.updateOne(
    { name: "Nitish" },
    { $set: { age: 29, city: "Andheri" } }
  )

> db.users.deleteOne({ name: "John" })

> db.users.drop()
true

> db.dropDatabase()

> exit
```

`use myappdb` does not create the database. Mongo creates it lazily on the first write, which is why `show dbs` won't list it until after the insert.

---

## Lessons learned

### 1. `ENV KEY: value` silently disabled authentication

The first Mongo Dockerfile was:

```dockerfile
ENV MONGO_INITDB_ROOT_USERNAME: root
ENV MONGO_INITDB_ROOT_PASSWORD: password
```

`ENV` accepts two forms:

```dockerfile
ENV key=value      # preferred
ENV key value      # legacy — everything after the first space is the value
```

There is no `=`, so Docker used the legacy form and split on the first space. The variable name became `MONGO_INITDB_ROOT_USERNAME:` — **colon included**. The colon is YAML syntax and means nothing in a Dockerfile.

Mongo looks for `MONGO_INITDB_ROOT_USERNAME`. It never found it, created no root user, and left authentication off. The container started cleanly and logged no error.

The evidence was visible in the session itself:

```bash
docker exec -it demos-mongodb-1 mongosh   # connected with no credentials
> show dbs                                 # and listed everything
```

With auth enabled, that is rejected. Combined with the port binding in Lesson 3, this was an open passwordless MongoDB reachable from the network — the configuration mass-targeted in the 2017 Mongo ransomware campaigns, and still actively scanned for today.

The general lesson is bigger than the syntax: **a database that starts successfully has not proven it is secure.** A silent misconfiguration is more dangerous than a crash, because a crash gets fixed. Verify explicitly rather than assuming.

```bash
docker compose exec mongodb env | grep MONGO
```

Every name should be bare — no trailing colon.

### 2. The Mongo data directory is `/data/db`

```dockerfile
VOLUME ["/var/lib/mongo/data"]    # nothing lives at this path
```

Mongo stores data in `/data/db` and cluster metadata in `/data/configdb`. The declared volume sat on an empty directory and persisted nothing; real data went to the image's own anonymous volume.

The two images differ, and guessing doesn't work:

| Image | Data directory |
|-------|----------------|
| `postgres` | `/var/lib/postgresql/data` |
| `mongo` | `/data/db`, `/data/configdb` |

Check instead of assuming:

```bash
docker image inspect mongo:7.0 --format '{{json .Config.Volumes}}'
```

### 3. `"27017:27017"` publishes to every interface

The short form binds on `0.0.0.0`. `docker ps` said so plainly:

```
0.0.0.0:27017->27017/tcp, [::]:27017->27017/tcp
```

On a server with a public IP, that database is on the internet. Scanners find open 5432 and 27017 within hours.

Binding to loopback keeps it host-only:

```yaml
ports:
  - "127.0.0.1:27017:27017"
```

For a GUI client on another machine, tunnel instead of exposing the port:

```bash
ssh -L 27017:localhost:27017 root@server
```

Containers on the same Docker network reach each other by service name regardless of publishing, so an app container never needs the port published at all.

### 4. An anonymous volume is a volume you can't manage

With no `volumes:` entry in Compose, Docker creates one named with a random hex ID. It persists data, but you can't easily find it, back it up, or tell which container owns it. After a few rebuild cycles `docker volume ls` is a list of orphaned hashes, each holding a database you can no longer identify.

Naming it makes `docker volume inspect pgdata` possible and makes `docker compose down -v` remove exactly what you expect.

### 5. `FROM mongo` means `latest`

An unpinned tag resolves to whatever `latest` points at on build day — a different major version next quarter, with different defaults. `postgres:14.24-alpine3.23` was pinned correctly; `FROM mongo` was not. Pin both.

### 6. Credentials in a Dockerfile are readable

Both Dockerfiles set passwords with `ENV`, which bakes them into an image layer:

```bash
docker history <image> --no-trunc | grep PASSWORD
```

That prints the password. So does `docker inspect`. Anything in a layer travels with the image — to a registry, to a colleague, into a CI cache.

Acceptable for a local practice exercise on a machine that publishes nothing. Not acceptable for anything real. Both images also support `POSTGRES_PASSWORD_FILE` and `MONGO_INITDB_ROOT_PASSWORD_FILE`, which read the secret from a file path instead.

### 7. The psql prompt tells you the parser state

Every syntax error in this session came from a missing semicolon:

```
practical=# SELECT * FROM employees      ← no semicolon
practical-# SELECT * FROM employees;     ← read as a continuation of line 1
ERROR:  syntax error at or near "SELECT"
```

The prompt character announces the state:

| Prompt | Meaning |
|--------|---------|
| `dbname=#` | ready for a new statement |
| `dbname-#` | mid-statement, waiting for `;` |
| `dbname'#` | inside an unclosed single-quoted string |
| `dbname"#` | inside an unclosed quoted identifier |
| `dbname(#` | inside unmatched parentheses |
| `dbname=*#` | inside an open transaction |

Anything other than `=#` means nothing has executed yet. `Ctrl+C` abandons the buffer.

Same cause here:

```
mydb=# drop database practical      ← no semicolon, nothing ran
mydb-# \l                           ← so it was still listed
```

Backslash commands (`\l`, `\dt`) need no semicolon. SQL statements always do.

---

## Command reference

### psql

| Command | Purpose |
|---------|---------|
| `\l` | list databases |
| `\c dbname` | connect to another database |
| `\dt` | list tables |
| `\d tablename` | describe a table |
| `\du` | list roles |
| `\x` | toggle expanded output — readable wide rows |
| `\timing` | show execution time per query |
| `\s` | command history |
| `\h CREATE TABLE` | syntax help for a statement |
| `\?` | help for backslash commands |
| `\q` | quit |

### mongosh

| Command | Purpose |
|---------|---------|
| `show dbs` | list databases |
| `use mydb` | switch database — created lazily on first write |
| `db` | current database name |
| `show collections` | list collections |
| `db.users.insertMany([...])` | insert documents |
| `db.users.find().pretty()` | read all documents, formatted |
| `db.users.findOne({ name: "Nitish" })` | read one document |
| `db.users.updateOne({...}, { $set: {...} })` | update a document |
| `db.users.deleteOne({...})` | delete a document |
| `db.users.countDocuments()` | count documents |
| `db.users.drop()` | drop a collection |
| `db.dropDatabase()` | drop the current database |
| `db.stats()` | database size and statistics |
| `exit` | quit |

Query operators:

```javascript
{ age: { $gt:  25 } }                  // greater than
{ age: { $gte: 25 } }                  // greater than or equal
{ age: { $lt:  25 } }                  // less than
{ age: { $ne:  25 } }                  // not equal
{ city: { $in: ["Mumbai", "Delhi"] } } // matches any in list
{ email: { $exists: true } }           // field is present
```

---

## Postgres vs MongoDB in Docker

| | PostgreSQL | MongoDB |
|---|---|---|
| Data directory | `/var/lib/postgresql/data` | `/data/db`, `/data/configdb` |
| Default port | 5432 | 27017 |
| Credential variables | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `MONGO_INITDB_ROOT_USERNAME`, `MONGO_INITDB_ROOT_PASSWORD` |
| Behaviour when unset | Refuses to start without `POSTGRES_PASSWORD` unless you explicitly opt out | **Starts with no authentication at all** |
| Shell | `psql -U myuser -d mydb` | `mongosh -u root -p --authenticationDatabase admin` |
| Auth database | the database being connected to | always `admin` for the root user |
| Creating a database | explicit `CREATE DATABASE` | implicit, on the first write after `use` |
| Statement terminator | `;` required | not required |

The row that matters is the fourth. Postgres refuses to start without a password unless you opt out deliberately. Mongo starts wide open and says nothing. One failure mode is loud and safe; the other is quiet and dangerous.

---

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| Mongo connects with no password | Auth never enabled. Check `ENV` syntax, then recreate with an empty volume — `docker compose down -v` |
| `Authentication failed` with the right password | Missing `--authenticationDatabase admin` |
| `role "postgres" does not exist` | `POSTGRES_USER` is `myuser`, so no `postgres` role exists. Use `-U myuser` |
| `database is being accessed by other users` | Drop it from a different connection |
| Data gone after a rebuild | Anonymous volume was replaced — use a named volume |
| `show dbs` doesn't list the new database | Mongo creates it on the first write; `use` alone creates nothing |
| `Connection refused` from another container | Use the service name and internal port (`postgresdb:5432`), not `localhost` |

Inspection commands:

```bash
docker compose ps
docker compose logs -f
docker volume ls
docker compose exec <service> env | grep -i pass
sudo ss -lntp | grep -E '5432|27017'
```

---

## Next

Seed the schema automatically instead of typing it into the shell — `.sql` and `.js` files placed in `/docker-entrypoint-initdb.d/` run on first initialization. Then move the credentials out of the Dockerfile into an environment file, and add a healthcheck so a dependent application container can wait for the database to be ready instead of crash-looping at startup.
