# Avakanta Backend — Makefile
# Todos los comandos asumen que se ejecutan desde back/avakanta_backend/
# Requiere: docker, docker compose, archivo .env presente

SHELL = /bin/bash

COMPOSE = docker compose
WEB     = web

.PHONY: help build up down restart logs logs-db shell bash migrate ps prune

help:
	@echo ""
	@echo "  Avakanta Backend — comandos disponibles"
	@echo ""
	@echo "  make build      Construir la imagen Docker"
	@echo "  make up         Levantar servicios en background"
	@echo "  make down       Detener y eliminar contenedores"
	@echo "  make restart    Reiniciar solo el contenedor web"
	@echo "  make logs       Seguir logs del contenedor web"
	@echo "  make logs-db    Seguir logs de la base de datos"
	@echo "  make shell      Abrir Django shell dentro del contenedor"
	@echo "  make bash       Abrir shell sh dentro del contenedor web"
	@echo "  make migrate    Ejecutar migraciones manualmente"
	@echo "  make ps         Estado de los contenedores"
	@echo "  make prune      Eliminar contenedores, volúmenes e imágenes del proyecto"
	@echo ""

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart $(WEB)

logs:
	$(COMPOSE) logs -f $(WEB)

logs-db:
	$(COMPOSE) logs -f db

shell:
	$(COMPOSE) exec $(WEB) python manage.py shell

bash:
	$(COMPOSE) exec $(WEB) /bin/sh

migrate:
	$(COMPOSE) exec $(WEB) python manage.py migrate --noinput

ps:
	$(COMPOSE) ps

prune:
	@echo "ADVERTENCIA: esto elimina contenedores, redes y volúmenes del proyecto."
	@read -p "¿Continuar? [s/N] " ans && [ "$$ans" = "s" ] || exit 1
	$(COMPOSE) down -v --rmi local
