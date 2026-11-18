#include "composer.h"

#include <clocale>
#include <stdexcept>
#include <utility>
#include <xkbcommon/xkbcommon-keysyms.h>

namespace windowsintl {
namespace {

const char *punctuation(xkb_keysym_t key) {
    switch (key) {
    case XKB_KEY_dead_acute: return "'";
    case XKB_KEY_dead_diaeresis: return "\"";
    case XKB_KEY_dead_grave: return "`";
    case XKB_KEY_dead_tilde: return "~";
    case XKB_KEY_dead_circumflex: return "^";
    default: return nullptr;
    }
}

std::string printableText(xkb_keysym_t key) {
    const auto codepoint = xkb_keysym_to_utf32(key);
    if (codepoint < 0x20 || (codepoint >= 0x7f && codepoint < 0xa0)) {
        return {};
    }
    char buffer[8];
    const auto length = xkb_keysym_to_utf8(key, buffer, sizeof(buffer));
    return length > 0 ? std::string(buffer, length - 1) : std::string();
}

std::string composedText(xkb_compose_state *state) {
    const auto length = xkb_compose_state_get_utf8(state, nullptr, 0);
    if (length <= 0) return {};
    std::string text(length + 1, '\0');
    xkb_compose_state_get_utf8(state, text.data(), text.size());
    text.resize(length);
    return text;
}

} // namespace

ComposeTable loadComposeTable() {
    auto context = std::unique_ptr<xkb_context, decltype(&xkb_context_unref)>(
        xkb_context_new(XKB_CONTEXT_NO_FLAGS), xkb_context_unref);
    if (!context) throw std::runtime_error("Cannot create XKB context");
    const auto *locale = std::setlocale(LC_CTYPE, nullptr);
    ComposeTable table(xkb_compose_table_new_from_locale(
                           context.get(), locale ? locale : "C",
                           XKB_COMPOSE_COMPILE_NO_FLAGS),
                       xkb_compose_table_unref);
    if (!table) throw std::runtime_error("Cannot load the user's Compose table");
    return table;
}

Composer::Composer(xkb_compose_table *table)
    : state_(xkb_compose_state_new(table, XKB_COMPOSE_STATE_NO_FLAGS),
             xkb_compose_state_unref) {
    if (!state_) throw std::runtime_error("Cannot create Compose state");
}

bool Composer::pending() const {
    return !punctuation_.empty();
}

void Composer::reset() {
    xkb_compose_state_reset(state_.get());
    punctuation_.clear();
}

Result Composer::feed(xkb_keysym_t key) {
    const auto *accent = punctuation(key);
    if (!pending() && !accent) return {};
    if (pending() && key == XKB_KEY_BackSpace) {
        reset();
        return {true, {}};
    }

    const auto text = accent ? std::string() : printableText(key);
    if (pending() && !accent && text.empty()) {
        reset();
        return {};
    }
    if (accent) punctuation_ += accent;

    xkb_compose_state_feed(state_.get(), key);
    switch (xkb_compose_state_get_status(state_.get())) {
    case XKB_COMPOSE_COMPOSING:
        return {true, {}};
    case XKB_COMPOSE_COMPOSED: {
        auto result = composedText(state_.get());
        reset();
        return {true, std::move(result)};
    }
    default: {
        auto result = punctuation_ + text;
        reset();
        return {true, std::move(result)};
    }
    }
}

} // namespace windowsintl
