#import "../Sources/DisplayConfig.h"
#include <assert.h>
#include <math.h>

int main(int argc, char **argv) {
    @autoreleasepool {
        const double cases[][3] = {{951,669,3}, {932,430,3}, {640,360,3}, {800,600,1}, {1000,1000,3}};
        for (unsigned i = 0; i < sizeof cases / sizeof *cases; i++) {
            double w = cases[i][0], h = cases[i][1], scale = cases[i][2];
            DMDisplaySize s = dm_display_size(w,h,scale);
            assert(s.width > 0 && s.height > 0 && !(s.width % 2) && !(s.height % 2));
            assert(s.width * s.height <= 2073600 && s.width <= w*scale && s.height <= h*scale);
            assert(fabs((double)s.width / s.height / (w/h) - 1) < .002);
            printf("%.0fx%.0f @%.0f -> %dx%d\n",w,h,scale,s.width,s.height);
        }
        assert(dm_display_size(393,852,3).width == 0);
        assert(dm_display_size(NAN,669,3).width == 0);
        assert(dm_display_size(951,669,0).width == 0);
        assert(dm_display_size(640,360,3).width == 1920);
        DMDisplaySize duo = dm_display_resolution("2670x1878", 951, 669, 3);
        assert(duo.width == 2670 && duo.height == 1878);
        assert(dm_display_resolution("2670x1878", 932, 430, 3).height == 1878);
        assert(dm_display_resolution("auto", 951, 669, 3).width == 1716);
        assert(dm_display_resolution("original", 951, 669, 3).width == 0);
        assert(dm_display_resolution("unknown", 951, 669, 3).width == 0);
        NSError *error = nil;
        assert(!dm_display_pak(@{}, (DMDisplaySize){1920,1080}, &error) && error);
        NSDictionary *manifest = @{@"profile": @"[Docked]\nr.setres=${DISPLAY_RESOLUTION}\n[Handheld]\nr.setres=${DISPLAY_RESOLUTION}\n",
            @"mount": @"../../../", @"path": @"Test/Config.ini"};
        NSData *pak = dm_display_pak(manifest, duo, &error);
        assert(pak && argc == 2 && [pak writeToFile:@(argv[1]) atomically:YES]);
        puts("PASS: active-window resolution budget, Duo native preset and pak writer");
    }
}
