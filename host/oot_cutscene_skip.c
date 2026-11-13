/* The active event's authored permission only: the game's controller still handles input, confirmation and completion. */
#include "../gpu/vk/vk_api.h"

int rx_option(int id, int otherwise);

uint64_t hos_oot_cutscene_skip_allowed(uint64_t native_allowed) {
    return rx_option(HOS_OPT_ALLOW_CUTSCENE_SKIP, 0) > 0 ? 1 : native_allowed;
}
