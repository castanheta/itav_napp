# Makefile for deploying and undeploying docker compose stack

# Load variables from .env if it exists
ifneq (,$(wildcard .env))
  include .env
  export
endif

DOCKER_COMPOSE := docker compose

.PHONY: all create-external-network remove-external-network deploy undeploy clean

all: deploy

create-external-network:
	echo ">>> Running script for creating external network..."
	docker network create shared
	echo ">>> Script finished."

remove-external-network:
	echo ">>> Running script for removing external network..."
	docker network rm -f shared
	echo ">>> Script finished."

deploy: create-external-network
	echo ">>> Starting Docker Compose services..."
	@if [ "$(PROVIDER_PROFILE)" = "True" ]; then \
		$(DOCKER_COMPOSE) --profile provider up --build -d; \
	else \
		$(DOCKER_COMPOSE) up --build -d --remove-orphans; \
	fi
	echo ">>> Deployment complete."

undeploy:
	echo ">>> Stopping and removing Docker Compose services..."
	$(DOCKER_COMPOSE) down
	echo ">>> Undeployment complete."

clean: undeploy remove-external-network
	echo ">>> Clean complete."
