.PHONY: all fmt fmt-fix clippy test doc build coverage patch-coverage audit

RUSTDOCFLAGS := -D rustdoc::broken-intra-doc-links -D rustdoc::private-intra-doc-links
PATCH_COVERAGE_BASE ?= main
PATCH_COVERAGE_FAIL_UNDER ?= 100
DIFF_COVER ?= diff-cover

all: fmt clippy test doc build

fmt:
	cargo fmt --check

fmt-fix:
	cargo fmt

clippy:
	cargo clippy --all-targets --locked -- -D warnings

test:
	cargo test --locked

doc:
	RUSTDOCFLAGS="$(RUSTDOCFLAGS)" cargo doc --no-deps --locked

build:
	cargo build --locked

coverage:
	cargo llvm-cov --workspace --fail-under-lines 90

patch-coverage:
	cargo llvm-cov --workspace --fail-under-lines 90 --lcov --output-path lcov.info
	$(DIFF_COVER) lcov.info --compare-branch=$(PATCH_COVERAGE_BASE) --fail-under=$(PATCH_COVERAGE_FAIL_UNDER)

audit:
	cargo audit
