.PHONY: all fmt fmt-fix lint test doc build coverage audit

all: fmt lint test doc build

fmt:
	@test -z "$$(gofumpt -l .)" || (gofumpt -l . && exit 1)

fmt-fix:
	gofumpt -w .

lint:
	golangci-lint run

test:
	go test ./...

doc:
	go vet ./...

build:
	go build ./cmd/stockchartsalerts

coverage:
	go test ./internal/... -coverprofile=coverage.out
	@echo "Checking per-package coverage (minimum 95%)..."
	@for pkg in $$(go list ./internal/...); do \
		pct=$$(go test $$pkg -cover 2>&1 | grep -oP 'coverage: \K[0-9.]+'); \
		if [ -z "$$pct" ]; then \
			echo "FAIL: Could not determine coverage for $$pkg"; \
			exit 1; \
		fi; \
		pct_int=$$(echo $$pct | cut -d. -f1); \
		if [ $$pct_int -lt 95 ]; then \
			echo "FAIL: $$pkg coverage $$pct% is below 95%"; \
			exit 1; \
		fi; \
		echo "  $$pkg: $$pct%"; \
	done
	@echo "Checking total coverage..."
	@go tool cover -func=coverage.out | tail -1 | awk '{gsub(/%/, "", $$NF); pct = $$NF; \
		print "Total coverage (internal packages): " pct "%"; \
		if (pct + 0 < 95) {print "FAIL: coverage below 95%"; exit 1} else {print "PASS: coverage >= 95%"}}'

audit:
	go run golang.org/x/vuln/cmd/govulncheck@latest ./...
