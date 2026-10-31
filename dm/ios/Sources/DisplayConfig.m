#import "DisplayConfig.h"
#import <CommonCrypto/CommonDigest.h>
#include <math.h>
#include <string.h>

DMDisplaySize dm_display_resolution(const char *mode, double width, double height, double scale) {
    if (!mode || !strcmp(mode, "auto")) return dm_display_size(width, height, scale);
    // Unfolded Duo nativeSize observed via devicectl, in landscape.
    // Its 2853 x 2007 logical pixel canvas is distinct from the panel resolution.
    if (!strcmp(mode, "2670x1878")) return (DMDisplaySize){2670, 1878};
    return (DMDisplaySize){0, 0};
}

DMDisplaySize dm_display_size(double width, double height, double scale) {
    if (!isfinite(width) || !isfinite(height) || !isfinite(scale) ||
        width < 2 || height < 2 || scale <= 0 || width / height < 1 || width / height > 3.6)
        return (DMDisplaySize){0, 0};
    double w = width * scale, h = height * scale;
    // No supersampling: at most a 1080p-sized pixel budget and 2520 on either axis.
    double k = fmin(1, fmin(sqrt(2073600.0 / (w * h)), 2520.0 / fmax(w, h)));
    return (DMDisplaySize){(int)floor(w * k / 2) * 2, (int)floor(h * k / 2) * 2};
}

static void u32(NSMutableData *d, uint32_t n) { n = CFSwapInt32HostToLittle(n); [d appendBytes:&n length:4]; }
static void u64(NSMutableData *d, uint64_t n) { n = CFSwapInt64HostToLittle(n); [d appendBytes:&n length:8]; }
static void fstr(NSMutableData *d, NSString *s) {
    NSData *b = [s dataUsingEncoding:NSUTF8StringEncoding]; u32(d, (uint32_t)b.length + 1);
    [d appendData:b]; uint8_t zero = 0; [d appendBytes:&zero length:1];
}
static void sha1(NSMutableData *d, NSData *b) {
    unsigned char digest[CC_SHA1_DIGEST_LENGTH];
    CC_SHA1(b.bytes, (CC_LONG)b.length, digest); [d appendBytes:digest length:sizeof digest];
}
NSData *dm_display_pak(NSDictionary *manifest, DMDisplaySize size, NSError **error) {
    NSString *profile = manifest[@"profile"], *mount = manifest[@"mount"], *path = manifest[@"path"];
    if (size.width < 2 || size.height < 2 || ![profile isKindOfClass:NSString.class] ||
        ![mount isKindOfClass:NSString.class] || ![path isKindOfClass:NSString.class] ||
        [[profile componentsSeparatedByString:@"${DISPLAY_RESOLUTION}"] count] != 3) {
        if (error) *error = [NSError errorWithDomain:@"DMDisplay" code:1
            userInfo:@{NSLocalizedDescriptionKey: @"Invalid automatic display profile"}];
        return nil;
    }
    NSString *res = [NSString stringWithFormat:@"%dx%d", size.width, size.height];
    NSData *data = [[profile stringByReplacingOccurrencesOfString:@"${DISPLAY_RESOLUTION}" withString:res]
        dataUsingEncoding:NSUTF8StringEncoding];
    // One uncompressed entry in Unreal's legacy v4 pak, matching uepak.py.
    NSMutableData *entry = [NSMutableData data];
    u64(entry, 0); u64(entry, data.length); u64(entry, data.length); u32(entry, 0);
    sha1(entry, data); uint8_t zero = 0; [entry appendBytes:&zero length:1]; u32(entry, 0);
    NSMutableData *pak = [entry mutableCopy]; [pak appendData:data];
    NSMutableData *index = [NSMutableData data]; fstr(index, mount); u32(index, 1); fstr(index, path); [index appendData:entry];
    uint64_t indexOffset = pak.length; [pak appendData:index];
    [pak appendBytes:&zero length:1]; u32(pak, 0x5A6F12E1); u32(pak, 4);
    u64(pak, indexOffset); u64(pak, index.length); sha1(pak, index);
    return pak;
}
