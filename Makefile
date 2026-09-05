.PHONY: preview up seed stop check

preview:
	cd frontend && npm ci && npm run demo

up:
	docker compose up --build -d --wait

seed:
	docker compose exec backend python seed_synthetic.py

stop:
	docker compose down

check:
	cd frontend && npm ci && npm run typecheck && npm run build:demo
