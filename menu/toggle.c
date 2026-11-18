/* setting.ap additions for the Customize row "Raiders: On/Off" (bank 0x4039fe00 + 0x600).
 *
 * The menu library shows per-row dynamic labels from menu+18+2*row while the byte at
 * menu+30 is non-zero; it is patched to accept 7 rows instead of 6, so row 6's label is
 * the halfword at menu+30. Our labels are setting strings 0x84 ("Raiders: Off") and
 * 0x85 ("Raiders: On"): low byte non-zero keeps the flag set.
 * Customize bit 6 (0x40) shows/hides main-menu position 6 (Raiders).
 * Only proven call paths: the menu library calls these through function pointers
 * (jalr), and they call stock MIPS16 code through odd function pointers. */
typedef volatile unsigned char vu8;
typedef int (*fn1)(char *);
#define CUSTOMIZE (*(vu8 *)0x9fc1d228)          /* setting.ap's system settings copy + 24 */
#define LABEL     ((CUSTOMIZE & 0x40) ? 0x85 : 0x84)
#define STOCK_CUSTOMIZE_ENTRY ((fn1)0x4039fe01)   /* original handler (MIPS16) */

/* Row handler for "Raiders: On/Off" (setting.mcg row 6 of Customize). */
__attribute__((section(".text.entry"), used, noinline)) int raiders_toggle(char *m)
{
    CUSTOMIZE ^= 0x40;
    *(volatile unsigned short *)(m + 30) = LABEL;
    *(volatile short *)(m + 2) = -1;
    *(volatile int *)(m + 8) = 0;
    *(volatile short *)(m + 12) = -1;
    return 0x8207;
}

/* Replaces Customize's entry handler in setting.mcg: run the stock one (it sets the
 * six stock labels and the flag), then add row 6's label. */
__attribute__((section(".text.wrap"), used, noinline)) int customize_entry(char *m)
{
    int r = STOCK_CUSTOMIZE_ENTRY(m);
    *(volatile unsigned short *)(m + 30) = LABEL;
    return r;
}
