#include "composer.h"

#include <memory>
#include <stdexcept>
#include <vector>
#include <fcitx-utils/key.h>
#include <fcitx/addonfactory.h>
#include <fcitx/addoninstance.h>
#include <fcitx/addonmanager.h>
#include <fcitx/event.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputcontextproperty.h>
#include <fcitx/instance.h>

namespace {

struct State : fcitx::InputContextProperty {
    explicit State(xkb_compose_table *table) : composer(table) {}
    windowsintl::Composer composer;
};

class WindowsCompose final : public fcitx::AddonInstance {
public:
    explicit WindowsCompose(fcitx::Instance *instance)
        : instance_(instance), table_(windowsintl::loadComposeTable()),
          factory_([this](fcitx::InputContext &) { return new State(table_.get()); }) {
        if (!instance_->inputContextManager().registerProperty("windowscompose", &factory_)) {
            throw std::runtime_error("windowscompose property is already registered");
        }
        handlers_.push_back(instance_->watchEvent(
            fcitx::EventType::InputContextKeyEvent,
            fcitx::EventWatcherPhase::PreInputMethod,
            [this](fcitx::Event &event) { keyEvent(static_cast<fcitx::KeyEvent &>(event)); }));
        for (auto type : {fcitx::EventType::InputContextFocusOut,
                          fcitx::EventType::InputContextReset,
                          fcitx::EventType::InputContextInputMethodDeactivated}) {
            handlers_.push_back(instance_->watchEvent(
                type, fcitx::EventWatcherPhase::PreInputMethod,
                [this](fcitx::Event &event) {
                    auto *ic = static_cast<fcitx::InputContextEvent &>(event).inputContext();
                    ic->propertyFor(&factory_)->composer.reset();
                }));
        }
    }

private:
    void keyEvent(fcitx::KeyEvent &event) {
        if (event.isRelease() || event.filtered() || event.accepted()) return;
        auto *ic = event.inputContext();
        auto &composer = ic->propertyFor(&factory_)->composer;
        const auto key = event.key();
        if (!instance_->inputMethod(ic).starts_with("keyboard-")) {
            composer.reset();
            return;
        }
        if (key.isModifier()) return;
        if (key.states().testAny(fcitx::KeyStates{
                fcitx::KeyState::Ctrl, fcitx::KeyState::Alt, fcitx::KeyState::Super})) {
            composer.reset();
            return;
        }
        // Multi_key belongs to the native engine, not this private state.
        if (!composer.pending() && instance_->isComposing(ic)) return;
        auto result = composer.feed(key.sym());
        if (!result.handled) return;
        event.filterAndAccept();
        if (!result.text.empty()) ic->commitString(result.text);
    }

    fcitx::Instance *instance_;
    windowsintl::ComposeTable table_;
    fcitx::FactoryFor<State> factory_;
    std::vector<std::unique_ptr<fcitx::HandlerTableEntry<fcitx::EventHandler>>> handlers_;
};

class Factory final : public fcitx::AddonFactory {
public:
    fcitx::AddonInstance *create(fcitx::AddonManager *manager) override {
        return new WindowsCompose(manager->instance());
    }
};

} // namespace

FCITX_ADDON_FACTORY_V2(windowscompose, Factory);
