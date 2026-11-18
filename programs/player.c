/* Frame (1-bit video) player for the SanDisk Clip Jam (ATJ2127), replacing video.ap's main.
 *
 * Runs as MIPS32 code in video.ap's bank at 0x4005fe00; video.ap's own launcher
 * (bank 0x4001fe00) calls play() as the app's main function. Everything else is
 * reached through existing firmware entry points:
 *   0xbfc1f5d5  video.ap's syscall stub for group 0xf (system):
 *                 0x0d open firmware file by name, 0x0f seek, 0x11 read,
 *                 0x1c millisecond timer, 0x31 sleep (ticks)
 *   0xbfc21331  drv_lcd: acquire LCD bus (pins are shared with NAND)
 *   0xbfc21379  drv_lcd: release LCD bus
 *   0x4849f989  applib: send async message (used to request the main menu)
 * The OLED is an SSD1306 on the LCD interface: bit0 of 0xc00d0008 selects
 * command(0)/data(1); bytes are written to 0xc00d0010.
 *
 * Frame data lives in the firmware file "dumy4m.bin" (a 4 MB 0xFF placeholder):
 *   0x000  "FRMS" u32 nframes u32 frame_us u32 reserved ...   (512-byte header)
 *   0x200  frames, 1024 bytes each, SSD1306 page order (8 pages x 128 columns,
 *          bit0 = top pixel of the page).
 */
typedef unsigned int u32;
typedef unsigned char u8;
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

/* scratch RAM inside video.ap's bss (0x9fc1d208..0x9fc1d6cc) */
#define NAME ((char *)0x9fc1d210)
#define MSG  ((u32 *)0x9fc1d200 + 0x0c)   /* 0x9fc1d230, 16 bytes */
#define BUF  ((u8 *)0x9fc1d280)           /* 1024 bytes -> 0x9fc1d680 */

#define FRAME 1024
#define HDR   512

static void lcd_cmd(u32 c)
{
    LCD_CTL &= ~1u;
    LCD_DATA = c;
}

static void blit(const u8 *p)
{
    LCD_LOCK();
    for (u32 page = 0; page < 8; page++) {
        lcd_cmd(0xb0 + page);
        lcd_cmd(0x00);
        lcd_cmd(0x10);
        LCD_CTL |= 1u;
        for (u32 x = 0; x < 128; x++)
            LCD_DATA = *p++;
    }
    LCD_UNLOCK();
}

static u32 now_ms(void) { return (u32)SYS(0, 0, 0, 0x1c); }

__attribute__((section(".text.entry"), used)) int play(void)
{
    const char *src = "dumy4m.bin";
    int i = 0;
    do NAME[i] = src[i]; while (src[i++]);

    int h = SYS(NAME, 0, 0, 0x0d);
    if (h) {
        SYS(h, 0, 0, 0x0f);
        if (SYS(h, BUF, HDR, 0x11) != -1 &&
            BUF[0] == 'F' && BUF[1] == 'R' && BUF[2] == 'M' && BUF[3] == 'S') {
            u32 n = BUF[4] | BUF[5] << 8 | BUF[6] << 16 | (u32)BUF[7] << 24;
            u32 us = BUF[8] | BUF[9] << 8 | BUF[10] << 16 | (u32)BUF[11] << 24;
            u32 t0 = now_ms();
            u32 held = 0, acc_us = 0;
            SYS(h, 0, HDR, 0x0f);
            for (u32 f = 0; f < n; f++) {
                if (SYS(h, BUF, FRAME, 0x11) == -1)
                    break;
                blit(BUF);
                /* any resistor-ladder key held for ~3 frames (after 1 s) exits */
                if (f > 15 && (KEY_ADC & 0x3f) < 50) {
                    if (++held >= 3)
                        break;
                } else {
                    held = 0;
                }
                acc_us += us;
                u32 due = t0 + acc_us / 1000;
                for (;;) {
                    int left = (int)(due - now_ms());
                    if (left <= 0)
                        break;
                    if (left >= 12)
                        SYS(1, 0, 0, 0x31);
                }
            }
        }
    }

    /* ask the manager (app 14) to start the main menu (app 15), like video.ap does */
    for (i = 0; i < 4; i++)
        MSG[i] = 0;
    MSG[0] = 0x201;
    ((u8 *)MSG)[4] = 0x0f;
    ((u8 *)MSG)[5] = 4;
    SEND_MSG(0x0e, MSG);
    return 0;
}
