/* "Sky Raiders": a small invaders-style shooter for the SanDisk Clip Jam (ATJ2127).
 *
 * Code lives in two places inside video.ap (whose original main never runs):
 *   .bank  0x4005fe00  video.ap bank (file 0x3c00, <= 0x800 bytes)  - entry + main loop
 *   .res   0xbfc1ee00  video.ap resident text (file 0x2800, <= 0x7c8 bytes; the
 *                      syscall stubs at 0xbfc1f5c8.. are kept)        - helpers + sprites
 * RAM: video.ap's bss 0x9fc1d208..0x9fc1d6cc (state struct + 1 KB framebuffer).
 *
 * Controls: a calibration screen asks for LEFT, RIGHT and FIRE (any keys on the
 * resistor ladder). Any other ladder key held briefly returns to the main menu.
 */
typedef unsigned int u32;
typedef int s32;
typedef unsigned char u8;
typedef volatile u32 vu32;
typedef volatile u8 vu8;
typedef int (*fn4)(int, int, int, int);
typedef void (*fn0)(void);

#ifndef HOST
#define RES  __attribute__((section(".res"), noinline, long_call))
#define BANK2 __attribute__((section(".bank2"), noinline))
#define RESD __attribute__((section(".res.data")))
#define ENTRY __attribute__((section(".text.entry"), used))

#define SYS(a0, a1, a2, f) (((fn4)0xbfc1f5d5)((int)(a0), (int)(a1), (int)(a2), (f)))
#define LCD_LOCK()   (((fn0)0xbfc21331)())
#define LCD_UNLOCK() (((fn0)0xbfc21379)())
#define SEND_MSG(app, msg) (((fn4)0x4849f989)((app), (int)(msg), 0, 0))
#define LCD_CTL  (*(vu32 *)0xc00d0008)
#define LCD_DATA (*(vu32 *)0xc00d0010)
#define KEY_ADC  (*(vu8 *)0xc002003c)
#endif  /* HOST: host_raiders.c provides these */

#define W 128
#define H 64
#define ROWS 4
#define COLS 7
#define AW 8            /* alien sprite width/height */
#define AH 6
#define DX 12           /* formation spacing */
#define DY 8
#define FORM_W ((COLS - 1) * DX + AW)
#define PY 58           /* player sprite top */
#define NAB 3           /* alien bullets */
#define NONE 7          /* key band: nothing pressed */

struct st {
    u32 alive;          /* bit r*COLS+c */
    s32 fx, fy, dir;    /* formation origin and direction */
    u32 tick, anim;
    s32 px;             /* player x */
    s32 bx, by;         /* player bullet (by < 0: none) */
    s32 abx[NAB], aby[NAB];
    u32 score, lives, wave, rnd;
    u32 kl, kr, kf;     /* calibrated key bands */
    u32 msg[4];
    u32 dead;           /* frames of death/explosion pause */
};
#ifndef HOST
#define G  ((struct st *)0x9fc1d208)     /* 0x6c bytes, ends before FB */
#define FB ((u8 *)0x9fc1d280)
#endif

/* ------------------------------------------------------------- resident helpers */
/* sprites: one byte per column, bit0 = top row */
RESD static const u8 ALIEN[2][2][AW] = {
    {{0x18, 0x3c, 0x16, 0x3f, 0x3f, 0x16, 0x3c, 0x18},   /* type A, frame 0 */
     {0x38, 0x1c, 0x36, 0x1f, 0x1f, 0x36, 0x1c, 0x38}},  /* type A, frame 1 */
    {{0x0e, 0x1b, 0x3e, 0x1b, 0x1b, 0x3e, 0x1b, 0x0e},   /* type B, frame 0 */
     {0x2e, 0x1b, 0x1e, 0x1b, 0x1b, 0x1e, 0x1b, 0x2e}}}; /* type B, frame 1 */
RESD static const u8 SHIP[9] = {0x0c, 0x0e, 0x0e, 0x0f, 0x0f, 0x0f, 0x0e, 0x0e, 0x0c};
RESD static const u8 ARROW_L[7] = {0x08, 0x1c, 0x3e, 0x7f, 0x1c, 0x1c, 0x1c};
RESD static const u8 ARROW_R[7] = {0x1c, 0x1c, 0x1c, 0x7f, 0x3e, 0x1c, 0x08};
RESD static const u8 FIRE[7] = {0x00, 0x60, 0x70, 0x7f, 0x70, 0x60, 0x00};   /* ship + shot */
RESD static const unsigned short DIG[10] = {      /* 3x5, row-major, bit14 = top-left */
    0x7b6f, 0x2c97, 0x73e7, 0x73cf, 0x5bc9, 0x79cf, 0x79ef, 0x7249, 0x7bef, 0x7bcf};
RESD static const u8 THR[7] = {4, 10, 16, 26, 32, 40, 50};

RES static void pset(s32 x, s32 y)
{
    if ((u32)x < W && (u32)y < H)
        FB[(y >> 3) * W + x] |= (u8)(1u << (y & 7));
}

/* draw a column-byte sprite, each pixel scaled s x s */
RES static void spr(const u8 *col, u32 n, s32 x, s32 y, u32 s)
{
    for (u32 c = 0; c < n; c++)
        for (u32 r = 0; r < 8; r++)
            if (col[c] >> r & 1)
                for (u32 i = 0; i < s; i++)
                    for (u32 j = 0; j < s; j++)
                        pset(x + c * s + i, y + r * s + j);
}

RES static void num(u32 v, s32 x, s32 y, u32 s)
{
    u32 d[5], n = 0;
    do d[n++] = v % 10; while ((v /= 10) && n < 5);
    while (n--) {
        u32 g = DIG[d[n]];
        for (u32 r = 0; r < 5; r++)
            for (u32 c = 0; c < 3; c++)
                if (g >> (14 - r * 3 - c) & 1)
                    for (u32 i = 0; i < s; i++)
                        for (u32 j = 0; j < s; j++)
                            pset(x + c * s + i, y + r * s + j);
        x += 4 * s;
    }
}

RES static void cls(void)
{
    for (u32 i = 0; i < 1024; i++)
        FB[i] = 0;
}

RES static void blit(void)
{
    const u8 *p = FB;
    LCD_LOCK();
    for (u32 page = 0; page < 8; page++) {
        LCD_CTL &= ~1u; LCD_DATA = 0xb0 + page;
        LCD_DATA = 0x00;
        LCD_DATA = 0x10;
        LCD_CTL |= 1u;
        for (u32 x = 0; x < W; x++)
            LCD_DATA = *p++;
    }
    LCD_UNLOCK();
}

RES static u32 now_ms(void) { return (u32)SYS(0, 0, 0, 0x1c); }

RES static void wait_until(u32 due)
{
    for (;;) {
        s32 left = (s32)(due - now_ms());
        if (left <= 0)
            return;
        if (left >= 12)
            SYS(1, 0, 0, 0x31);
    }
}

RES static u32 band(void)
{
    u32 v = KEY_ADC & 0x3f;
    for (u32 i = 0; i < 7; i++)
        if (v < THR[i])
            return i;
    return NONE;
}

RES static u32 rnd(void)
{
    G->rnd = G->rnd * 1103515245u + 12345u;
    return G->rnd >> 16;
}

/* show a prompt and return the band of the key pressed (after release) */
BANK2 static u32 ask(const u8 *icon)
{
    u32 b, same = 0, last = NONE;
    cls();
    spr(icon, 7, 50, 18, 4);
    blit();
    while (band() != NONE)
        SYS(2, 0, 0, 0x31);
    for (;;) {                          /* debounce: same band for 3 polls */
        SYS(2, 0, 0, 0x31);
        b = band();
        same = (b == last) ? same + 1 : 0;
        last = b;
        if (b != NONE && same >= 2)
            break;
    }
    while (band() != NONE)
        SYS(2, 0, 0, 0x31);
    return b;
}

BANK2 static void new_wave(void)
{
    G->alive = (1u << (ROWS * COLS)) - 1;
    G->fx = 4;
    G->fy = 9 + (G->wave < 4 ? G->wave * 2 : 8);
    G->dir = 2;
    G->bx = -1; G->by = -1;
    for (u32 i = 0; i < NAB; i++)
        G->aby[i] = -1;
}

/* ------------------------------------------------------------- main (bank) */
RES static void back_to_menu(void)
{
    for (u32 i = 0; i < 4; i++)
        G->msg[i] = 0;
    G->msg[0] = 0x201;
    ((u8 *)G->msg)[4] = 0x0f;
    ((u8 *)G->msg)[5] = 4;
    SEND_MSG(0x0e, G->msg);
}

RES static u32 count(u32 m)
{
    u32 n = 0;
    while (m) { n += m & 1; m >>= 1; }
    return n;
}

/* Alien side of one frame: march, fire, move shots, hit the player.
 * Lives in a second video.ap bank (0x4009fe00); called once per frame. */
BANK2 static void aliens_step(u32 left)
{
    if (++G->tick >= 1 + left / 2) {         /* faster as the formation thins out */
        G->tick = 0;
        G->anim ^= 1;
        s32 lo = COLS, hi = -1, bottom = 0;
        for (u32 i = 0; i < ROWS * COLS; i++)
            if (G->alive >> i & 1) {
                s32 c = i % COLS, r = i / COLS;
                if (c < lo) lo = c;
                if (c > hi) hi = c;
                if (r > bottom) bottom = r;
            }
        s32 nx = G->fx + G->dir;
        if (nx + lo * DX < 0 || nx + hi * DX + AW > W) {
            G->dir = -G->dir;
            G->fy += 3;
        } else
            G->fx = nx;
        if (G->fy + bottom * DY + AH >= PY && !G->dead) {   /* invaded */
            G->lives = 0;
            G->dead = 45;
        }
    }
    if ((rnd() & 31) < 2 + G->wave && !G->dead) {
        u32 c = rnd() % COLS;
        for (s32 r = ROWS - 1; r >= 0; r--)
            if (G->alive >> (r * COLS + c) & 1) {
                for (u32 i = 0; i < NAB; i++)
                    if (G->aby[i] < 0) {
                        G->abx[i] = G->fx + c * DX + AW / 2;
                        G->aby[i] = G->fy + r * DY + AH;
                        break;
                    }
                break;
            }
    }
    for (u32 i = 0; i < NAB; i++)
        if (G->aby[i] >= 0) {
            G->aby[i] += 1 + (G->tick & 1);
            if (G->aby[i] >= H) G->aby[i] = -1;
            else if (!G->dead && G->aby[i] >= PY && G->abx[i] >= G->px && G->abx[i] < G->px + 9) {
                G->aby[i] = -1;
                G->lives--;
                G->dead = 45;
            }
        }
}

ENTRY int raiders(void)
{
    G->rnd = now_ms();
    G->kl = ask(ARROW_L);
    G->kr = ask(ARROW_R);
    G->kf = ask(FIRE);

restart:
    G->score = 0; G->lives = 3; G->wave = 0; G->px = 60; G->dead = 0;
    new_wave();
    u32 t = now_ms(), quit = 0;

    for (;;) {
        u32 k = band();
        if (k != NONE && k != G->kl && k != G->kr && k != G->kf) {
            if (++quit >= 4) { back_to_menu(); return 0; }
        } else quit = 0;

        if (G->dead) {
            if (--G->dead == 0) {
                if (!G->lives)
                    break;
                G->px = 60;
            }
        } else {
            /* player */
            if (k == G->kl && G->px > 0) G->px -= 2;
            if (k == G->kr && G->px < W - 9) G->px += 2;
            if (k == G->kf && G->by < 0) { G->bx = G->px + 4; G->by = PY - 3; }
        }
        /* player bullet vs aliens */
        if (G->by >= 0) {
            G->by -= 3;
            s32 cx = G->bx - G->fx, cy = G->by - G->fy;
            if (cx >= 0 && cy >= 0 && cx % DX < AW && cy % DY < AH) {
                u32 c = cx / DX, r = cy / DY;
                if (c < COLS && r < ROWS && (G->alive >> (r * COLS + c) & 1)) {
                    G->alive &= ~(1u << (r * COLS + c));
                    G->score += (ROWS - r) * 10;
                    G->by = -1;
                }
            }
            if (G->by < 7) G->by = -1;
        }
        u32 left = count(G->alive);
        if (!left) {                          /* wave cleared */
            G->wave++;
            new_wave();
        }
        aliens_step(left);

        /* draw */
        cls();
        num(G->score, 0, 0, 1);
        for (u32 i = 0; i < G->lives; i++)
            spr(SHIP, 9, W - 10 - i * 11, 0, 1);
        for (u32 i = 0; i < ROWS * COLS; i++)
            if (G->alive >> i & 1)
                spr(ALIEN[(i / COLS) >> 1][G->anim], AW, G->fx + (i % COLS) * DX, G->fy + (i / COLS) * DY, 1);
        if (!G->dead || (G->dead & 4))
            spr(SHIP, 9, G->px, PY, 1);
        if (G->by >= 0)
            for (u32 j = 0; j < 3; j++) pset(G->bx, G->by + j);
        for (u32 i = 0; i < NAB; i++)
            if (G->aby[i] >= 0) {
                pset(G->abx[i], G->aby[i]);
                pset(G->abx[i] + ((G->aby[i] >> 1) & 1), G->aby[i] + 1);
                pset(G->abx[i], G->aby[i] + 2);
            }
        blit();
        t += 33;                               /* ~30 fps */
        wait_until(t);
    }

    /* game over: big score until FIRE (restart) or another key (menu) */
    cls();
    num(G->score, 20, 22, 4);
    blit();
    for (u32 i = 0; i < 60; i++)            /* ignore keys for ~1.2 s */
        SYS(2, 0, 0, 0x31);
    for (;;) {
        u32 k = band();
        if (k == G->kf || k == G->kl || k == G->kr) {
            while (band() != NONE) SYS(2, 0, 0, 0x31);
            goto restart;
        }
        if (k != NONE) { back_to_menu(); return 0; }
        SYS(2, 0, 0, 0x31);
    }
}
