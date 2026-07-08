/* pico8-stretch: LD_PRELOAD shim for pico8_dyn on the Bit0.
 *
 * The raspi build only stretches its 128x128 back page in the custom
 * "rpi" blitter (pixel_perfect 0), which calls desktop-GL functions that
 * Mesa's strict GLES2 rejects -> black screen. On the working SDL-renderer
 * path (pixel_perfect 1) it insists on integer scaling: 1x on a 240px-tall
 * panel. This shim rewrites the destination rect of the back-page
 * SDL_RenderCopy to PICO8_DRAW_RECT ("x,y,w,h", default 40,0,240,240:
 * square, pixel-aspect, centered on the 320x240 panel).
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { int x, y, w, h; } SDL_Rect;

static int (*real_copy)(void *, void *, const SDL_Rect *, const SDL_Rect *);
static int (*real_copyex)(void *, void *, const SDL_Rect *, const SDL_Rect *,
			  double, const void *, int);
static int (*real_query)(void *, unsigned *, int *, int *, int *);
static SDL_Rect target;
static int ready;

static const SDL_Rect *maybe_stretch(void *tex, const SDL_Rect *dst)
{
	int w = 0, h = 0;
	if (!dst || !real_query)
		return dst;
	if (real_query(tex, NULL, NULL, &w, &h) != 0)
		return dst;
	if (w != 128 || h != 128)	/* only the pico-8 back page */
		return dst;
	if (!ready) {
		const char *e = getenv("PICO8_DRAW_RECT");
		target = (SDL_Rect){40, 0, 240, 240};
		if (e)
			sscanf(e, "%d,%d,%d,%d",
			       &target.x, &target.y, &target.w, &target.h);
		ready = 1;
	}
	return &target;
}

int SDL_RenderCopy(void *r, void *tex, const SDL_Rect *src, const SDL_Rect *dst)
{
	if (!real_copy) {
		real_copy = dlsym(RTLD_NEXT, "SDL_RenderCopy");
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
		real_query = dlsym(RTLD_NEXT, "SDL_QueryTexture");
	}
	return real_copyex(r, tex, src, maybe_stretch(tex, dst),
			   angle, center, flip);
}
