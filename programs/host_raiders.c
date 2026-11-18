/* Host test harness: runs raiders.c on the Mac with fake hardware.
 * A scripted key timeline drives calibration, play and exit; selected frames
 * are written as PBM images. Build: cc -DHOST host_raiders.c -o host_raiders */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HOST
#define RES   __attribute__((noinline))
#define BANK2 __attribute__((noinline))
#define RESD
#define ENTRY

static unsigned char fb_mem[1024];
static unsigned int g_mem[64];
static unsigned int fake_ms, blits, sent_app = 0xff;
static unsigned char adc_val = 63;

static void adc_script(void);
static int sys(int a0, int a1, int a2, int f)
{
    (void)a1; (void)a2;
    if (f == 0x1c) { fake_ms += 1; adc_script(); return (int)fake_ms; }
    if (f == 0x31) { fake_ms += 10 * a0; adc_script(); return 0; }
    fprintf(stderr, "unexpected sys fn %#x\n", f);
    exit(1);
}
static void dump(const char *name);
static void lock(void) {}
static void unlock(void)
{
    blits++;
    if (blits % 150 == 0 || blits == 3) {
        char n[64];
        snprintf(n, sizeof n, "host_frames/f%05u.pbm", blits);
        dump(n);
    }
}
static int send(int app, const unsigned char *msg)
{
    unsigned type = msg[0] | msg[1] << 8;
    if (app != 0x0e || type != 0x201) { fprintf(stderr, "bad message app=%d type=%#x\n", app, type); exit(1); }
    sent_app = msg[4];
    return 0;
}

#define SYS(a0, a1, a2, f) sys((int)(long)(a0), (int)(long)(a1), (int)(long)(a2), (f))
#define LCD_LOCK() lock()
#define LCD_UNLOCK() unlock()
#define SEND_MSG(app, msg) send((app), (const unsigned char *)(msg))
static unsigned int lcd_ctl, lcd_data;
#define LCD_CTL lcd_ctl
#define LCD_DATA lcd_data
#define KEY_ADC adc_val
#define G  ((struct st *)g_mem)
#define FB fb_mem

#include "raiders.c"

/* key timeline (ms): calibrate L=band0, R=band1, F=band2, then play, then exit (band3) */
static void adc_script(void)
{
    unsigned t = fake_ms;
    unsigned char v = 63;
    if (t >= 200 && t < 400) v = 2;          /* LEFT  -> band 0 */
    else if (t >= 700 && t < 900) v = 8;     /* RIGHT -> band 1 */
    else if (t >= 1200 && t < 1400) v = 12;  /* FIRE  -> band 2 */
    else if (t >= 2000 && t < 60000) {       /* play: weave and fire, with releases */
        unsigned p = (t / 400) % 6;
        v = p < 2 ? 12 : p < 4 ? (t / 2400 % 2 ? 2 : 8) : 12;
        if (t % 1000 >= 900) v = 63;
    } else if (t >= 60000 && t < 61000) v = 63;
    else if (t >= 61000) v = 20;             /* other key -> back to menu */
    adc_val = v;
}

static void dump(const char *name)
{
    FILE *f = fopen(name, "w");
    fprintf(f, "P1\n128 64\n");
    for (int y = 0; y < 64; y++) {
        for (int x = 0; x < 128; x++)
            fputs(fb_mem[(y >> 3) * 128 + x] >> (y & 7) & 1 ? "1 " : "0 ", f);
        fputc('\n', f);
    }
    fclose(f);
}

int main(void)
{
    int r = raiders();
    printf("returned %d after %u ms, %u frames; keys L=%u R=%u F=%u; score=%u lives=%u wave=%u; msg app=%#x\n",
           r, fake_ms, blits, G->kl, G->kr, G->kf, G->score, G->lives, G->wave, sent_app);
    return 0;
}
