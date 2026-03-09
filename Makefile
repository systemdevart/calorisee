PROJECT_DIR := $(shell pwd)
BACKEND_PORT := 8100
PID_FILE := /tmp/calorisee-backend.pid
LOG_FILE := /tmp/calorisee-backend.log

.PHONY: deploy stop start build nginx

deploy: stop build start nginx
	@echo "Deployed! https://calorisee.chebakov.me"

build:
	cd $(PROJECT_DIR)/frontend && npm run build

stop:
	@if [ -f $(PID_FILE) ]; then \
		kill $$(cat $(PID_FILE)) 2>/dev/null || true; \
		rm -f $(PID_FILE); \
	fi
	@sleep 1

start:
	cd $(PROJECT_DIR) && \
		nohup python3 -m uvicorn backend.app:app \
			--host 127.0.0.1 --port $(BACKEND_PORT) \
			> $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE)
	@echo "Backend started on port $(BACKEND_PORT), PID: $$(cat $(PID_FILE))"

nginx:
	sudo nginx -t && sudo systemctl reload nginx
