#import <Foundation/Foundation.h>

typedef struct { int width, height; } DMDisplaySize;
// Use the active window's point dimensions and screen scale, not mainScreen.
DMDisplaySize dm_display_size(double width, double height, double scale);
// Fixed presets use their full pixel dimensions; Auto retains its pixel budget.
// Original and unknown modes return zero (the caller handles Original separately).
DMDisplaySize dm_display_resolution(const char *mode, double width, double height, double scale);
// The manifest contains the user's extracted, tokenized Unreal device profile.
NSData *dm_display_pak(NSDictionary *manifest, DMDisplaySize size, NSError **error);
