

## Postgre 15

```shell
docker run -d \
  --name pg15 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=123456 \
  -e POSTGRES_DB=postgre \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  --restart unless-stopped \
  postgres:15-alpine
```

## Base Command
```shell

docker ps

docker exec -it pg15 /bin/bash
psql -h 127.0.0.1 -U postgres -W

```