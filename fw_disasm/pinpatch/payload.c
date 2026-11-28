/* PIN gate payload for the Lanchonlh HG-UV98 (V1.1 dump), linked at 0x0804A000.
 *
 * Hook: the boot scene at 0x0801B71C has its instruction at 0x0801B7A8
 * ("adds.w r7, r5, #0x142") replaced with "b.w _start".  The stub runs the
 * gate, re-executes the displaced instruction and resumes at 0x0801B7AC.
 *
 * Firmware entry points used (V1.1 image, verified by disassembly):
 *   0x0801B9B0  display_set_window(y0, x0, y1, x1)   (0x2A/0x2B)
 *   0x0801BA52  tft_write_cmd(byte)
 *   0x0801BA74  tft_write_byte(byte)
 *   0x0801D31C  display_blit_image(y, x, rows, cols, img, len)   boot splash
 *   0x0802819A  key_scan() -> ladder index, sets the group flags
 *   0x080294F8  adc/keys init (ADC1+ADC2 clock, calibration, key mutex)
 *
 * Drawing goes straight to the panel (no stack tiles): the UI task stack is
 * about 1 KB, and 256-byte buffers were enough to fault before the first
 * pixel.  Colour writes use the same sequence as the firmware's own
 * display_fill_rect, including the PC2 wrap.
 *
 * Keys (recovered key tables): 0..9 digits, 10 = MENU (confirm),
 * 11/12 = UP/DOWN, 13 = AB (backspace), 14 = '*', 15 = '#'.
 */

typedef unsigned char  u8;
typedef unsigned short u16;
typedef unsigned int   u32;

/* |1 = Thumb bit: the calls go through function pointers (blx rN), and a
 * zero bit would make the core switch to ARM state and fault. */
#define A_SETWIN   0x0801B9B1u
#define A_CMD      0x0801BA53u
#define A_BYTE     0x0801BA75u
#define A_BLIT     0x0801D31Du
#define A_SCAN     0x0802819Bu
#define A_ADCINIT  0x080294F9u

typedef void (*setwin_fn)(u16 y0, u16 x0, u16 y1, u16 x1);
typedef void (*cmd_fn)(u8 cmd);
typedef void (*byte_fn)(u8 b);
typedef void (*blit_fn)(u8 y, u8 x, u8 rows, u8 cols, const u8 *img, u32 len);
typedef u8   (*scan_fn)(void);
typedef void (*adcinit_fn)(void);

#define SETWIN ((setwin_fn)A_SETWIN)
#define CMD    ((cmd_fn)A_CMD)
#define BYTE   ((byte_fn)A_BYTE)
#define BLIT   ((blit_fn)A_BLIT)
#define SCAN   ((scan_fn)A_SCAN)

#define GPIOC_BSRR (*(volatile u32 *)0x40011010u)
#define GPIOC_BRR  (*(volatile u32 *)0x40011014u)
#define LCD_SEL     2u

#define FLAG_A (*(volatile u8 *)0x20005160u)
#define FLAG_B (*(volatile u8 *)0x20005161u)
#define FLAG_C (*(volatile u8 *)0x20005162u)

#define ADC2_CR2 (*(volatile u32 *)0x40012808u)

#define SPLASH     ((const u8 *)0x08004130u)
#define SPLASH_LEN 0xA000u

#define KEY_CONFIRM 10u
#define KEY_BACK    13u

#define C_BLACK  0x0000u
#define C_WHITE  0xFFFFu
#define C_BLUE   0x001Fu
#define C_RED    0xF800u
#define C_YELLOW 0xFFE0u
#define C_GREY   0x8410u

extern const u8 font8x16[];

/* Patched by patch_password.py; defined in pinblob.c (a separate TU so GCC
 * cannot constant-fold the patched bytes and drop the gate).
 *   0..3 magic "PWN1", 4 length (0 = disabled), 5..10 digits, 11 xor. */
extern volatile u8 pin_blob[16];

static u8 key_code(void)
{
    static const u8 map_a[8] = { 10u, 11u, 12u, 13u, 1u, 2u, 3u, 14u };
    static const u8 map_b[8] = {  4u,  5u,  6u,  0u, 7u, 8u, 9u, 15u };
    static const u8 map_c[3] = { 18u, 19u, 20u };
    u8 idx = SCAN();

    if (FLAG_A == 1u)
        return map_a[idx & 7u];
    if (FLAG_B == 1u)
        return map_b[idx & 7u];
    if (FLAG_C == 1u)
        return (idx < 3u) ? map_c[idx] : 0xFFu;
    return 0xFFu;
}

/* Solid rectangle, streamed straight to the panel (same sequence as the
 * stock display_fill_rect: PC2 wrap, window, 0x2C, pixels). */
static void fill_area(u16 y, u16 x, u16 w, u16 h, u16 color)
{
    u32 n = (u32)w * (u32)h;

    GPIOC_BRR = LCD_SEL;
    SETWIN(y, x, (u16)(y + h - 1u), (u16)(x + w - 1u));
    CMD(0x2Cu);
    while (n != 0u) {
        BYTE((u8)(color >> 8));
        BYTE((u8)color);
        n--;
    }
    GPIOC_BSRR = LCD_SEL;
}

/* 8x16 glyph cell: 16 rows x 8 columns, no buffer. */
static void draw_cell(u16 y, u16 x, const u8 *rec, u16 fg, u16 bg)
{
    u8 r, c;

    GPIOC_BRR = LCD_SEL;
    SETWIN(y, x, (u16)(y + 15u), (u16)(x + 7u));
    CMD(0x2Cu);
    for (r = 0u; r < 8u; r++) {
        for (c = 0u; c < 8u; c++) {
            u16 col = (((rec[c] >> r) & 1u) != 0u) ? fg : bg;
            BYTE((u8)(col >> 8));
            BYTE((u8)col);
        }
    }
    for (r = 0u; r < 8u; r++) {
        for (c = 0u; c < 8u; c++) {
            u16 col = (((rec[8u + c] >> r) & 1u) != 0u) ? fg : bg;
            BYTE((u8)(col >> 8));
            BYTE((u8)col);
        }
    }
    GPIOC_BSRR = LCD_SEL;
}

static void draw_text(u16 y, u16 x, const char *s, u16 fg, u16 bg)
{
    while (*s != 0) {
        u8 c = (u8)*s++;
        if (c >= 0x20u && c <= 0x7Eu)
            draw_cell(y, x, &font8x16[(u16)(c - 0x20u) * 16u], fg, bg);
        x = (u16)(x + 8u);
    }
}

static void draw_stars(u8 pos)
{
    char st[7];
    u8 i;

    fill_area(68u, 40u, 80u, 16u, C_BLACK);
    for (i = 0u; i < 6u; i++)
        st[i] = (i < pos) ? '*' : ' ';
    st[6] = 0;
    draw_text(68u, 56u, st, C_WHITE, C_BLACK);
}

static void draw_static(void)
{
    fill_area(0u, 0u, 160u, 128u, C_BLACK);
    draw_text(24u, 28u, "RADIO IS LOCK", C_RED, C_BLACK);
    draw_text(48u, 44u, "PASSWORD:", C_YELLOW, C_BLACK);
    draw_text(108u, 22u, "ENTER PASSWORD", C_GREY, C_BLACK);
}

static void show_error(void)
{
    draw_text(88u, 24u, "WRONG PASSWORD", C_RED, C_BLACK);
}

static void clear_error(void)
{
    fill_area(88u, 24u, 112u, 16u, C_BLACK);
}

void pin_gate(void)
{
    u8 len = pin_blob[4];
    u8 buf[6];
    u8 pos = 0u;
    u8 i;
    u8 k;
    u8 err = 0u;
    u32 guard;

    if (len < 4u || len > 6u)
        return;                       /* not provisioned: normal boot */

    if ((ADC2_CR2 & 1u) == 0u)
        ((adcinit_fn)A_ADCINIT)();    /* enable/calibrate ADC2 for the keys */

    draw_static();
    draw_stars(0u);

    for (;;) {
        k = 0xFFu;
        while (k == 0xFFu)
            k = key_code();

        guard = 0u;
        while (key_code() != 0xFFu && guard < 4000000u)
            guard++;

        if (err != 0u) {
            clear_error();
            err = 0u;
        }

        if (k <= 9u) {
            if (pos < 6u) {
                buf[pos] = k;
                pos++;
                draw_stars(pos);
            }
        } else if (k == KEY_BACK) {
            if (pos != 0u) {
                pos--;
                draw_stars(pos);
            }
        } else if (k == KEY_CONFIRM) {
            if (pos != 0u) {
                u8 ok = (pos == len) ? 1u : 0u;
                if (ok != 0u)
                    for (i = 0u; i < len; i++)
                        if (buf[i] != pin_blob[5u + i])
                            ok = 0u;
                if (ok != 0u) {
                    BLIT(0u, 0u, 128u, 160u, SPLASH, SPLASH_LEN);
                    return;
                }
                pos = 0u;
                draw_stars(0u);
                show_error();
                err = 1u;
            }
        }
    }
}
