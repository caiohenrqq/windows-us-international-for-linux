#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <fcitx-utils/capabilityflags.h>
#include <fcitx-utils/event.h>
#include <fcitx-utils/key.h>
#include <fcitx-utils/keysymgen.h>
#include <fcitx/addonmanager.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/event.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputpanel.h>
#include <fcitx/instance.h>

namespace {

void require(bool condition, const std::string &message) {
    if (!condition) throw std::runtime_error(message);
}

class Client final : public fcitx::InputContext {
public:
    explicit Client(fcitx::Instance &instance)
        : fcitx::InputContext(instance.inputContextManager(), "windowsintl-test") {
        setCapabilityFlags(fcitx::CapabilityFlag::Preedit);
        created();
        focusIn();
    }
    ~Client() override { destroy(); }
    const char *frontend() const override { return "windowsintl-test"; }

    bool press(fcitx::Key key) {
        fcitx::KeyEvent event(this, key);
        const bool handled = keyEvent(event);
        fcitx::KeyEvent release(this, key, true);
        keyEvent(release);
        return handled;
    }
    void clear() {
        reset();
        committed.clear();
        visiblePreedits = 0;
    }

    std::string committed;
    int visiblePreedits = 0;

protected:
    void commitStringImpl(const std::string &text) override { committed += text; }
    void deleteSurroundingTextImpl(int, unsigned int) override {}
    void forwardKeyImpl(const fcitx::ForwardKeyEvent &) override {}
    void updatePreeditImpl() override {
        if (!inputPanel().clientPreedit().empty()) ++visiblePreedits;
    }
};

} // namespace

void runTests(fcitx::Instance &instance) {
    require(instance.addonManager().addon("windowscompose") != nullptr,
            "Built addon did not load");
    Client first(instance), second(instance);
    require(instance.inputMethod(&first) == "keyboard-us", "Unexpected keyboard engine");

    first.press(fcitx::Key(FcitxKey_dead_acute));
    require(first.committed.empty() && first.visiblePreedits == 0,
            "Pending dead key became visible");
    first.press(fcitx::Key(FcitxKey_e));
    require(first.committed == "é" && first.visiblePreedits == 0,
            "Accented text was not committed silently");

    first.clear();
    first.press(fcitx::Key(FcitxKey_dead_acute));
    first.press(fcitx::Key(FcitxKey_Shift_L));
    first.press(fcitx::Key(FcitxKey_E, fcitx::KeyState::Shift));
    require(first.committed == "É", "Shift interrupted uppercase composition");

    first.clear();
    first.press(fcitx::Key(FcitxKey_dead_acute));
    require(!first.press(fcitx::Key(FcitxKey_Right)), "First arrow was swallowed");
    require(first.committed.empty(), "Arrow inserted punctuation");
    require(!first.press(fcitx::Key(FcitxKey_e)), "Pending accent survived navigation");

    first.clear();
    first.press(fcitx::Key(FcitxKey_dead_acute));
    first.press(fcitx::Key(FcitxKey_c, fcitx::KeyState::Ctrl));
    require(first.committed.empty(), "Shortcut committed pending punctuation");
    require(!first.press(fcitx::Key(FcitxKey_e)), "Shortcut did not cancel the accent");

    first.clear();
    first.press(fcitx::Key(FcitxKey_dead_acute));
    first.focusOut();
    first.focusIn();
    require(!first.press(fcitx::Key(FcitxKey_e)), "Accent leaked across focus changes");

    first.clear();
    second.clear();
    first.press(fcitx::Key(FcitxKey_dead_acute));
    second.press(fcitx::Key(FcitxKey_dead_tilde));
    first.press(fcitx::Key(FcitxKey_e));
    second.press(fcitx::Key(FcitxKey_a));
    require(first.committed == "é" && second.committed == "ã", "Contexts shared state");

    first.clear();
    first.press(fcitx::Key(FcitxKey_Multi_key));
    first.press(fcitx::Key(FcitxKey_m));
    first.press(fcitx::Key(FcitxKey_s));
    require(first.committed == "😄", "Native emoji Compose shortcut changed");
    require(first.visiblePreedits > 0, "Native Compose preedit was disabled globally");

    first.clear();
    first.press(fcitx::Key(FcitxKey_Multi_key));
    first.press(fcitx::Key(FcitxKey_dead_acute));
    first.press(fcitx::Key(FcitxKey_e));
    require(first.committed == "custom", "Dead key interrupted a native Compose shortcut");

    std::cout << "Fcitx addon loading, preedit, navigation, shortcuts and focus: OK\n";
}

class TestAddon final : public fcitx::AddonInstance {
public:
    explicit TestAddon(fcitx::Instance *instance) {
        deferred_ = instance->eventLoop().addDeferEvent([instance](fcitx::EventSource *) {
            try {
                runTests(*instance);
                instance->exit(0);
            } catch (const std::exception &error) {
                std::cerr << error.what() << '\n';
                instance->exit(1);
            }
            return true;
        });
    }
private:
    std::unique_ptr<fcitx::EventSource> deferred_;
};

class TestFactory final : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        return new TestAddon(manager->instance());
    }
};

FCITX_ADDON_FACTORY_V2(windowsintltest, TestFactory);
