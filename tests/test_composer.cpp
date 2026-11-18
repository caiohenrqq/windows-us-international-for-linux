#include "composer.h"

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <xkbcommon/xkbcommon-keysyms.h>

using windowsintl::Composer;

namespace {

void require(bool condition, const std::string &message) {
    if (!condition) throw std::runtime_error(message);
}

windowsintl::ComposeTable compile(const std::string &source) {
    auto *context = xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    auto *table = xkb_compose_table_new_from_buffer(
        context, source.data(), source.size(), "en_US.UTF-8",
        XKB_COMPOSE_FORMAT_TEXT_V1, XKB_COMPOSE_COMPILE_NO_FLAGS);
    xkb_context_unref(context);
    require(table != nullptr, "Compose fixture did not compile");
    return {table, xkb_compose_table_unref};
}

struct Case {
    xkb_keysym_t accent;
    xkb_keysym_t letter;
    std::string expected;
};

void testMappings(xkb_compose_table *table) {
    const std::vector<Case> cases = {
        {XKB_KEY_dead_acute, XKB_KEY_a, "á"},
        {XKB_KEY_dead_acute, XKB_KEY_e, "é"},
        {XKB_KEY_dead_acute, XKB_KEY_c, "ç"},
        {XKB_KEY_dead_acute, XKB_KEY_C, "Ç"},
        {XKB_KEY_dead_acute, XKB_KEY_m, "'m"},
        {XKB_KEY_dead_acute, XKB_KEY_s, "'s"},
        {XKB_KEY_dead_acute, XKB_KEY_y, "ý"},
        {XKB_KEY_dead_acute, XKB_KEY_space, "'"},
        {XKB_KEY_dead_grave, XKB_KEY_e, "è"},
        {XKB_KEY_dead_grave, XKB_KEY_n, "`n"},
        {XKB_KEY_dead_circumflex, XKB_KEY_e, "ê"},
        {XKB_KEY_dead_circumflex, XKB_KEY_2, "^2"},
        {XKB_KEY_dead_tilde, XKB_KEY_a, "ã"},
        {XKB_KEY_dead_tilde, XKB_KEY_o, "õ"},
        {XKB_KEY_dead_tilde, XKB_KEY_e, "~e"},
        {XKB_KEY_dead_diaeresis, XKB_KEY_u, "ü"},
        {XKB_KEY_dead_diaeresis, XKB_KEY_y, "ÿ"},
        {XKB_KEY_dead_diaeresis, XKB_KEY_Y, "\"Y"},
        {XKB_KEY_dead_diaeresis, XKB_KEY_space, "\""},
        {XKB_KEY_dead_acute, XKB_KEY_dead_acute, "''"},
        {XKB_KEY_dead_acute, xkb_utf32_to_keysym(0x1f642), "'🙂"},
    };
    for (const auto &test : cases) {
        Composer composer(table);
        auto pending = composer.feed(test.accent);
        require(pending.handled && pending.text.empty() && composer.pending(),
                "A dead key must be silent and pending");
        auto result = composer.feed(test.letter);
        require(result.handled && result.text == test.expected,
                "Wrong composed text; expected " + test.expected + ", got " + result.text);
        require(!composer.pending(), "Composition did not finish");
    }
}

void testNavigation(xkb_compose_table *table) {
    for (auto key : {XKB_KEY_Left, XKB_KEY_Right, XKB_KEY_Up, XKB_KEY_Down,
                     XKB_KEY_Home, XKB_KEY_End, XKB_KEY_Page_Up, XKB_KEY_Page_Down,
                     XKB_KEY_Tab, XKB_KEY_Return, XKB_KEY_Escape,
                     XKB_KEY_Delete, XKB_KEY_F1}) {
        Composer composer(table);
        composer.feed(XKB_KEY_dead_acute);
        const auto result = composer.feed(key);
        require(!result.handled && result.text.empty() && !composer.pending(),
                "Navigation must cancel the accent and pass through");
        require(!composer.feed(XKB_KEY_e).handled, "Accent leaked past navigation");
    }
    Composer composer(table);
    composer.feed(XKB_KEY_dead_acute);
    require(composer.feed(XKB_KEY_BackSpace).handled && !composer.pending(),
            "Backspace must cancel without deleting text");
    require(!composer.feed(XKB_KEY_BackSpace).handled,
            "Backspace without a pending accent must pass through");
}

void testIndependentContexts(xkb_compose_table *table) {
    Composer first(table), second(table);
    first.feed(XKB_KEY_dead_acute);
    second.feed(XKB_KEY_dead_tilde);
    require(first.feed(XKB_KEY_e).text == "é", "First context leaked");
    require(second.feed(XKB_KEY_a).text == "ã", "Second context leaked");
    first.feed(XKB_KEY_dead_acute);
    first.reset();
    require(!first.feed(XKB_KEY_e).handled, "Explicit reset did not cancel");
}

void testNativeStateIsUntouched(xkb_compose_table *table) {
    auto *native = xkb_compose_state_new(table, XKB_COMPOSE_STATE_NO_FLAGS);
    xkb_compose_state_feed(native, XKB_KEY_Multi_key);
    xkb_compose_state_feed(native, XKB_KEY_m);
    Composer composer(table);
    composer.feed(XKB_KEY_dead_acute);
    composer.reset();
    xkb_compose_state_feed(native, XKB_KEY_s);
    require(xkb_compose_state_get_status(native) == XKB_COMPOSE_COMPOSED,
            "Private composition disturbed Multi_key");
    char text[16];
    xkb_compose_state_get_utf8(native, text, sizeof(text));
    require(std::string(text) == "😄", "Native Compose shortcut changed");
    xkb_compose_state_unref(native);
    require(!composer.feed(XKB_KEY_apostrophe).handled,
            "A literal apostrophe (including ABNT2) must pass through");
    require(!composer.feed(XKB_KEY_ccedilla).handled,
            "A literal cedilla must pass through");
}

void testLongCustomResult() {
    const std::string expected(255, 'x');
    auto table = compile("<dead_acute> <e> : \"" + expected + "\"\n");
    Composer composer(table.get());
    composer.feed(XKB_KEY_dead_acute);
    require(composer.feed(XKB_KEY_e).text == expected, "Custom result was truncated");
}

} // namespace

int main(int argc, char **argv) {
    try {
        require(argc == 2, "Pass the generated Compose file path");
        const std::string source = "include \"%L\"\ninclude \"" +
            std::string(argv[1]) + "\"\n<Multi_key> <m> <s> : \"😄\"\n";
        auto table = compile(source);
        testMappings(table.get());
        testNavigation(table.get());
        testIndependentContexts(table.get());
        testNativeStateIsUntouched(table.get());
        testLongCustomResult();
        std::cout << "Composition, navigation, context isolation and custom rules: OK\n";
        return EXIT_SUCCESS;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
