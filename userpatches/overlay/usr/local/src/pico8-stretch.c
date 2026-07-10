/* pico8-stretch: LD_PRELOAD shim for pico8_dyn on the Bit0.
 *
 * The raspi build only stretches its 128x128 back page in the custom
 * "rpi" blitter (pixel_perfect 0), which calls desktop-GL functions that
 * Mesa's strict GLES2 rejects -> black screen. On the working SDL-renderer
 * path (pixel_perfect 1) it insists on integer scaling: 1x on a 240px-tall
 * panel. This shim does two things:
 *
 * 1. Rendering – rewrites the destination rect of the back-page
 *    SDL_RenderCopy to PICO8_DRAW_RECT ("x,y,w,h", default 40,0,240,240:
 *    square, pixel-aspect, centered on the 320x240 panel).
 *
 * 2. Mouse input – PICO-8 maps SDL window coordinates to its 128x128 canvas
 *    assuming the canvas sits at its natural 1x integer-scaled position
 *    (centered in the window: 96,56 for a 320x240 display). The stretch rect
 *    above moved the rendered canvas elsewhere, so raw SDL coords are wrong.
 *    We intercept SDL_GetMouseState and SDL_PollEvent and apply the inverse
 *    transform so PICO-8's internal math yields the correct canvas position.
 *
 *    Transform: remap(raw) = pico8_off + pico8_scale*(raw - draw.xy)*128/draw.wh
 *    pico8_off/scale are derived from the SDL window size captured at
 *    SDL_CreateWindow time (defaults: off=96,56 scale=1 for 320x240).
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── minimal SDL2 types ──────────────────────────────────────────────────── */
typedef struct { int x, y, w, h; } SDL_Rect;
typedef unsigned int  Uint32;
typedef signed int    Sint32;
typedef unsigned char Uint8;

typedef struct {
	Uint32 type, timestamp, windowID, which, state;
	Sint32 x, y, xrel, yrel;
} SDL_MouseMotionEvent;
 
typedef struct {
	Uint32 type, timestamp, windowID, which;
	Uint8  button, state, clicks, padding1;
	Sint32 x, y;
} SDL_MouseButtonEvent;

typedef union {
	Uint32               type;
	SDL_MouseMotionEvent motion;
	SDL_MouseButtonEvent button;
	Uint8                padding[56];
} SDL_Event;

#define SDL_MOUSEMOTION     0x400u
#define SDL_MOUSEBUTTONDOWN 0x401u
#define SDL_MOUSEBUTTONUP   0x402u

/* ── shared state ────────────────────────────────────────────────────────── */
static int (*real_copy)(void *, void *, const SDL_Rect *, const SDL_Rect *);
static int (*real_copyex)(void *, void *, const SDL_Rect *, const SDL_Rect *,
			  double, const void *, int);
static int (*real_query)(void *, unsigned *, int *, int *, int *);
static Uint32 (*real_getmousestate)(int *, int *);
static int    (*real_pollevent)(SDL_Event *);
static void * (*real_createwindow)(const char *, int, int, int, int, Uint32);

static SDL_Rect target;		/* PICO8_DRAW_RECT – where canvas is rendered */
static int target_ready;

/* Where PICO-8 *thinks* the 128x128 canvas is (1x integer scale, centered).
 * Defaults for the 320x240 panel: scale=1, off_x=96, off_y=56.            */
static int pico8_off_x = 96;
static int pico8_off_y = 56;
static int pico8_scale = 1;

/* ── helpers ─────────────────────────────────────────────────────────────── */
static void ensure_target(void)
{
	if (target_ready) return;
	const char *e = getenv("PICO8_DRAW_RECT");
	target = (SDL_Rect){40, 0, 240, 240};
	if (e)
		sscanf(e, "%d,%d,%d,%d",
		       &target.x, &target.y, &target.w, &target.h);
	target_ready = 1;
}

/* Remap a real SDL window coordinate to the pre-shim canvas position that
 * PICO-8's internal mouse→canvas math expects.                              */
static Sint32 remap_x(Sint32 x)
{
	if (!target.w) return x;
	return (Sint32)(pico8_off_x
	                + pico8_scale * (x - target.x) * 128.0 / target.w
	                + 0.5);
}
static Sint32 remap_y(Sint32 y)
{
	if (!target.h) return y;
	return (Sint32)(pico8_off_y
	                + pico8_scale * (y - target.y) * 128.0 / target.h
	                + 0.5);
}

static const SDL_Rect *maybe_stretch(void *tex, const SDL_Rect *dst)
{
	int w = 0, h = 0;
	if (!dst || !real_query)
		return dst;
	if (real_query(tex, NULL, NULL, &w, &h) != 0)
		return dst;
	if (w != 128 || h != 128)	/* only the pico-8 back page */
		return dst;
	ensure_target();
	return &target;
}

/* ── intercepted SDL calls ───────────────────────────────────────────────── */

/* Capture window dimensions so we can derive PICO-8's canvas offset. */
void *SDL_CreateWindow(const char *title, int x, int y, int w, int h,
		       Uint32 flags)
{
	if (!real_createwindow)
		real_createwindow = dlsym(RTLD_NEXT, "SDL_CreateWindow");
	if (w > 0 && h > 0) {
		int s = (w < h ? w : h) / 128;
		if (s < 1) s = 1;
		pico8_scale = s;
		pico8_off_x = (w - 128 * s) / 2;
		pico8_off_y = (h - 128 * s) / 2;
	}
	ensure_target();
	return real_createwindow(title, x, y, w, h, flags);
}

/* Remap polled mouse position. */
Uint32 SDL_GetMouseState(int *x, int *y)
{
	if (!real_getmousestate)
		real_getmousestate = dlsym(RTLD_NEXT, "SDL_GetMouseState");
	Uint32 buttons = real_getmousestate(x, y);
	ensure_target();
	if (x) *x = (int)remap_x((Sint32)*x);
	if (y) *y = (int)remap_y((Sint32)*y);
	return buttons;
}

/* Remap mouse coordinates inside queued events. */
int SDL_PollEvent(SDL_Event *ev)
{
	if (!real_pollevent)
		real_pollevent = dlsym(RTLD_NEXT, "SDL_PollEvent");
	int r = real_pollevent(ev);
	if (r && ev) {
		ensure_target();
		if (ev->type == SDL_MOUSEMOTION) {
			ev->motion.x = remap_x(ev->motion.x);
			ev->motion.y = remap_y(ev->motion.y);
		} else if (ev->type == SDL_MOUSEBUTTONDOWN ||
			   ev->type == SDL_MOUSEBUTTONUP) {
			ev->button.x = remap_x(ev->button.x);
			ev->button.y = remap_y(ev->button.y);
		}
	}
	return r;
}

int SDL_RenderCopy(void *r, void *tex, const SDL_Rect *src, const SDL_Rect *dst)
{
	if (!real_copy) {
		real_copy  = dlsym(RTLD_NEXT, "SDL_RenderCopy");
		real_query = dlsym(RTLD_NEXT, "SDL_QueryTexture");
	}
	return real_copy(r, tex, src, maybe_stretch(tex, dst));
}

int SDL_RenderCopyEx(void *r, void *tex, const SDL_Rect *src,
		     const SDL_Rect *dst, double angle, const void *center,
		     int flip)
{
	if (!real_copyex) {
		real_copyex = dlsym(RTLD_NEXT, "SDL_RenderCopyEx");
		real_query  = dlsym(RTLD_NEXT, "SDL_QueryTexture");
	}
	return real_copyex(r, tex, src, maybe_stretch(tex, dst),
			   angle, center, flip);
}
