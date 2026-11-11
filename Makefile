CC     ?= gcc
CFLAGS  = -O2 -Wall -Wextra -std=c99 -Isrc
ifeq ($(OS),Windows_NT)
EXT = dll
else ifeq ($(shell uname -s),Darwin)
EXT = dylib
else
EXT = so
endif
SRC = src/leftist_heap.c src/game.c

all: lib build/test_heap build/sim

lib: build/libdispatch.$(EXT)

build/libdispatch.$(EXT): $(SRC) src/game.h src/leftist_heap.h
	@mkdir -p build
	$(CC) $(CFLAGS) -fPIC -shared -o $@ $(SRC)

build/test_heap: src/test_heap.c src/leftist_heap.c
	@mkdir -p build
	$(CC) $(CFLAGS) -o $@ $^ -lm

build/sim: src/sim.c $(SRC)
	@mkdir -p build
	$(CC) $(CFLAGS) -o $@ $^

test: build/test_heap
	./build/test_heap

sim: build/sim
	./build/sim

play: lib
	python3 gui/main.py

clean:
	rm -rf build

.PHONY: all lib test sim play clean
