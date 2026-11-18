#pragma once

#include <memory>
#include <string>
#include <xkbcommon/xkbcommon-compose.h>

namespace windowsintl {

using ComposeTable = std::unique_ptr<xkb_compose_table,
                                     decltype(&xkb_compose_table_unref)>;

ComposeTable loadComposeTable();

struct Result {
    bool handled = false;
    std::string text;
};

class Composer {
public:
    explicit Composer(xkb_compose_table *table);
    bool pending() const;
    void reset();
    Result feed(xkb_keysym_t key);

private:
    std::unique_ptr<xkb_compose_state, decltype(&xkb_compose_state_unref)> state_;
    std::string punctuation_;
};

} // namespace windowsintl
