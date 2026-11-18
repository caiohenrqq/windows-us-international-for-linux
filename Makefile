CXX ?= c++
PYTHON ?= python3
PKG_CONFIG ?= pkg-config
PROJECT_CPPFLAGS = -Isrc $(shell $(PKG_CONFIG) --cflags Fcitx5Core Fcitx5Utils xkbcommon)
CXXFLAGS ?= -O2 -g
PROJECT_CXXFLAGS = -std=c++20 -Wall -Wextra -Werror -fPIC -MMD -MP
PROJECT_LIBS = $(shell $(PKG_CONFIG) --libs Fcitx5Core Fcitx5Utils xkbcommon)
OBJECTS = build/addon.o build/composer.o

.PHONY: all check check-dependencies check-sanitizers clean install uninstall
all: check-dependencies build/libwindowscompose.so

check-dependencies:
	$(PKG_CONFIG) --atleast-version=5.1.23 Fcitx5Core

build:
	mkdir -p $@

build/%.o: src/%.cpp | build
	$(CXX) $(CPPFLAGS) $(PROJECT_CPPFLAGS) $(CXXFLAGS) $(PROJECT_CXXFLAGS) -c $< -o $@

build/libwindowscompose.so: $(OBJECTS)
	$(CXX) -shared $(LDFLAGS) $^ $(PROJECT_LIBS) $(LDLIBS) -o $@

build/test-composer: tests/test_composer.cpp src/composer.cpp src/composer.h | build
	$(CXX) $(CPPFLAGS) $(PROJECT_CPPFLAGS) $(CXXFLAGS) $(PROJECT_CXXFLAGS) tests/test_composer.cpp src/composer.cpp $(LDFLAGS) $(PROJECT_LIBS) $(LDLIBS) -o $@

build/libwindowsintltest.so: tests/test_fcitx.cpp | build
	$(CXX) $(CPPFLAGS) $(PROJECT_CPPFLAGS) $(CXXFLAGS) $(PROJECT_CXXFLAGS) -shared $< $(LDFLAGS) $(PROJECT_LIBS) $(LDLIBS) -o $@

build/test-composer-sanitized: tests/test_composer.cpp src/composer.cpp src/composer.h | build
	$(CXX) -Isrc -std=c++20 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer tests/test_composer.cpp src/composer.cpp $(shell $(PKG_CONFIG) --cflags --libs xkbcommon) -o $@

check-sanitizers: build/test-composer-sanitized
	./build/test-composer-sanitized "$(CURDIR)/data/compose/windows-us-intl"

check: all build/test-composer build/libwindowsintltest.so
	$(PYTHON) tools/generate_compose.py --check
	./build/test-composer "$(CURDIR)/data/compose/windows-us-intl"
	$(PYTHON) tests/run_fcitx_test.py
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

install: all
	$(PYTHON) tools/install.py install

uninstall:
	$(PYTHON) tools/install.py uninstall

clean:
	rm -rf build

-include $(OBJECTS:.o=.d)
