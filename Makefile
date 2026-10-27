CXX ?= c++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Wpedantic

flowforge: src/main.cpp
	$(CXX) $(CXXFLAGS) $< -o $@

test:
	python3 tests/regression.py

.PHONY: test
