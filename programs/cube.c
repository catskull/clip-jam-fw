/* Real-time spinning wireframe cube for the SanDisk Clip Jam (ATJ2127).
 * Same harness as player.c: MIPS32 code in video.ap's bank at 0x4005fe00, called
 * as the app's main by video.ap's launcher. Integer-only maths (Q12 sine table),
 * perspective projection, Bresenham lines into a 1 KB SSD1306-layout framebuffer.
 * Hold any front/volume key to return to the main menu.
 */
typedef unsigned int u32;
typedef int s32;
typedef unsigned char u8;
typedef short s16;
typedef volatile u32 vu32;
typedef volatile u8 vu8;

typedef int (*fn4)(int, int, int, int);
typedef void (*fn0)(void);

#define SYS(a0, a1, a2, f) (((fn4)0xbfc1f5d5)((int)(a0), (int)(a1), (int)(a2), (f)))
#define LCD_LOCK()   (((fn0)0xbfc21331)())
#define LCD_UNLOCK() (((fn0)0xbfc21379)())
#define SEND_MSG(app, msg) (((fn4)0x4849f989)((app), (int)(msg), 0, 0))

#define LCD_CTL  (*(vu32 *)0xc00d0008)
#define LCD_DATA (*(vu32 *)0xc00d0010)
#define KEY_ADC  (*(vu8 *)0xc002003c)

#define MSG ((u32 *)0x9fc1d230)
#define FB  ((u8 *)0x9fc1d280)          /* 1024 bytes, inside video.ap's bss */

#define W 128
#define H 64

static const s16 SIN_Q[65] = {
    0, 101, 201, 301, 401, 501, 601, 700, 799, 897, 995, 1092, 1189, 1285, 1380, 1474,
    1567, 1660, 1751, 1842, 1931, 2019, 2106, 2191, 2276, 2359, 2440, 2520, 2598, 2675,
    2751, 2824, 2896, 2967, 3035, 3102, 3166, 3229, 3290, 3349, 3406, 3461, 3513, 3564,
    3612, 3659, 3703, 3745, 3784, 3822, 3857, 3889, 3920, 3948, 3973, 3996, 4017, 4036,
    4052, 4065, 4076, 4085, 4091, 4095, 4096};

/* angle: 256 per turn; result Q12 */
static s32 isin(u32 a)
{
    a &= 255;
    if (a < 64) return SIN_Q[a];
    if (a < 128) return SIN_Q[128 - a];
    if (a < 192) return -SIN_Q[a - 128];
    return -SIN_Q[256 - a];
}
static s32 icos(u32 a) { return isin(a + 64); }

static void pset(s32 x, s32 y)
{
    if ((u32)x < W && (u32)y < H)
        FB[(y >> 3) * W + x] |= (u8)(1u << (y & 7));
}

static void line(s32 x0, s32 y0, s32 x1, s32 y1)
{
    s32 dx = x1 > x0 ? x1 - x0 : x0 - x1, sx = x0 < x1 ? 1 : -1;
    s32 dy = y1 > y0 ? y0 - y1 : y1 - y0, sy = y0 < y1 ? 1 : -1;
    s32 err = dx + dy;
    for (;;) {
        pset(x0, y0);
        if (x0 == x1 && y0 == y1)
            break;
        s32 e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

static void lcd_cmd(u32 c)
{
    LCD_CTL &= ~1u;
    LCD_DATA = c;
}

static void blit(void)
{
    const u8 *p = FB;
    LCD_LOCK();
    for (u32 page = 0; page < 8; page++) {
        lcd_cmd(0xb0 + page);
        lcd_cmd(0x00);
        lcd_cmd(0x10);
        LCD_CTL |= 1u;
        for (u32 x = 0; x < W; x++)
            LCD_DATA = *p++;
    }
    LCD_UNLOCK();
}

static u32 now_ms(void) { return (u32)SYS(0, 0, 0, 0x1c); }

/* cube corners: bit0 -> x, bit1 -> y, bit2 -> z ; edges join corners differing in one bit */
static const u8 EDGES[12][2] = {
    {0, 1}, {2, 3}, {4, 5}, {6, 7},
    {0, 2}, {1, 3}, {4, 6}, {5, 7},
    {0, 4}, {1, 5}, {2, 6}, {3, 7}};

#define S    256      /* half edge length, model units */
#define DIST 700      /* camera distance */
#define FOC  34       /* focal length; worst-case corner projects to ~28 px */

__attribute__((section(".text.entry"), used)) int cube(void)
{
    s32 px[8], py[8];
    u32 t0 = now_ms(), held = 0, frames = 0;

    for (;;) {
        u32 t = now_ms() - t0;
        /* constant angular speeds, independent of frame rate */
        u32 ax = t / 23, ay = t / 17, az = t / 41;
        s32 sx = isin(ax), cx = icos(ax);
        s32 sy = isin(ay), cy = icos(ay);
        s32 sz = isin(az), cz = icos(az);

        for (u32 i = 0; i < 8; i++) {
            s32 x = (i & 1) ? S : -S;
            s32 y = (i & 2) ? S : -S;
            s32 z = (i & 4) ? S : -S;
            s32 t1;
            /* rotate about X */
            t1 = (y * cx - z * sx) >> 12;
            z = (y * sx + z * cx) >> 12;
            y = t1;
            /* about Y */
            t1 = (x * cy + z * sy) >> 12;
            z = (z * cy - x * sy) >> 12;
            x = t1;
            /* about Z */
            t1 = (x * cz - y * sz) >> 12;
            y = (x * sz + y * cz) >> 12;
            x = t1;
            s32 d = z + DIST;
            px[i] = W / 2 + (x * FOC) / d;
            py[i] = H / 2 - (y * FOC) / d;
        }

        for (u32 i = 0; i < 1024; i++)
            FB[i] = 0;
        for (u32 e = 0; e < 12; e++) {
            u32 a = EDGES[e][0], b = EDGES[e][1];
            line(px[a], py[a], px[b], py[b]);
        }
        blit();
        frames++;

        if (frames > 30 && (KEY_ADC & 0x3f) < 50) {
            if (++held >= 3)
                break;
        } else {
            held = 0;
        }
        /* ~40 fps cap; yield a tick so the rest of the system keeps running */
        u32 due = t0 + t + 25;
        SYS(1, 0, 0, 0x31);
        for (;;) {
            s32 left = (s32)(due - now_ms());
            if (left <= 0)
                break;
            if (left >= 12)
                SYS(1, 0, 0, 0x31);
        }
    }

    for (u32 i = 0; i < 4; i++)
        MSG[i] = 0;
    MSG[0] = 0x201;
    ((u8 *)MSG)[4] = 0x0f;
    ((u8 *)MSG)[5] = 4;
    SEND_MSG(0x0e, MSG);
    return 0;
}
