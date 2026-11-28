/* PIN slot, separate translation unit: GCC must not constant-fold the
 * patched bytes (a same-TU static array with a known initializer made the
 * whole gate look dead and the linker dropped it). */
typedef unsigned char u8;

__attribute__((section(".pinblob"), used))
volatile u8 pin_blob[16] = {
    'P', 'W', 'N', '1',
    0u,
    0u, 0u, 0u, 0u, 0u, 0u,
    0u,
    0u, 0u, 0u, 0u
};
