// Simulator-only integration probe. No game code, assets, or shaders are loaded.
#import "../../Sources/front_ios.m"
uint64_t g_t0_ns;
uint64_t now_ns(void) { return (uint64_t)(CACurrentMediaTime()*1e9); }
void dm_audio_suspend(int x) {} void dm_audio_reset(void) {}
void dm_focus_set(int x) {} void guest_clock_freeze_for(int a,int b) {} void dm_gfx_suspend(int x) {}
void dm_haptics_apple_init(void) {} void dm_gamepad_reset(void) {}
UIView *dm_gamepad_view(CGRect f) { return [[UIView alloc] initWithFrame:f]; }
bool dm_show_launcher(void *v,void (*done)(void)) { return false; }
int front_ios_boot_ok(void) { return 1; }
uint64_t mtl_present_count(void) { return 0; }
static void sample_display(void) {
    DmRootVC *root=g_root; DmGameView *game=root.game;
    [root.view layoutIfNeeded]; [game layoutIfNeeded];
    UIWindow *window=root.view.window; UIWindowScene *scene=window.windowScene;
    UIScreen *screen=scene.screen; CAMetalLayer *layer=(CAMetalLayer*)game.layer;
    BOOL fill=CGRectEqualToRect(game.frame,root.view.bounds) &&
        CGSizeEqualToSize(root.view.bounds.size,window.bounds.size) &&
        CGSizeEqualToSize(window.bounds.size,scene.coordinateSpace.bounds.size) &&
        CGSizeEqualToSize(window.bounds.size,screen.bounds.size);
    DMDisplaySize output=dm_display_size(game.bounds.size.width,game.bounds.size.height,screen.nativeScale);
    double configured=strtod(getenv("DM_CAMERA_ASPECT")?:"0",NULL);
    BOOL matches=output.height && fabs(configured-(double)output.width/output.height)<0.00001;
    NSDictionary *result=@{@"passed":@(fill),@"window":NSStringFromCGRect(window.bounds),
      @"root":NSStringFromCGRect(root.view.bounds),@"game":NSStringFromCGRect(game.frame),
      @"scene":NSStringFromCGRect(scene.coordinateSpace.bounds),@"screen":NSStringFromCGRect(screen.bounds),
      @"native":NSStringFromCGRect(screen.nativeBounds),@"scale":@(screen.scale),@"nativeScale":@(screen.nativeScale),
      @"safeArea":NSStringFromUIEdgeInsets(root.view.safeAreaInsets),@"drawable":NSStringFromCGSize(layer.drawableSize),
      @"resolutionMatchesCurrentWindow":@(matches),@"plannedOutput":@[@(output.width),@(output.height)],
      @"orientation":@(scene.interfaceOrientation),@"aspect":@(getenv("DM_CAMERA_ASPECT")?:""),
      @"overlay":@(getenv("DM_ROMFS_OVERLAY")?:"")};
    NSString *doc=NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,NSUserDomainMask,YES)[0];
    [[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil] writeToFile:[doc stringByAppendingPathComponent:@"checks.json"] atomically:YES];
    static UILabel *label; static CAShapeLayer *grid; static id<MTLCommandQueue> queue;
    if (!label) {
        label=[UILabel new]; label.numberOfLines=0; label.textAlignment=NSTextAlignmentCenter;
        label.font=[UIFont monospacedSystemFontOfSize:19 weight:UIFontWeightMedium];label.textColor=UIColor.whiteColor;
        label.backgroundColor=[UIColor colorWithWhite:0 alpha:0.6];
        [root.view addSubview:label];
        grid=[CAShapeLayer layer];grid.strokeColor=UIColor.yellowColor.CGColor;grid.fillColor=UIColor.clearColor.CGColor;grid.lineWidth=2;
        [game.layer addSublayer:grid]; queue=[layer.device newCommandQueue];
    }
    CGRect bounds=game.bounds;
    UIBezierPath *path=[UIBezierPath bezierPathWithRect:CGRectInset(bounds,5,5)];
    CGFloat referenceHeight=bounds.size.width*9.0/16;
    [path appendPath:[UIBezierPath bezierPathWithRect:CGRectMake(5,(bounds.size.height-referenceHeight)/2,bounds.size.width-10,referenceHeight)]];
    grid.path=path.CGPath;
    label.frame=CGRectMake(40,bounds.size.height/2-95,bounds.size.width-80,190);
    label.text=[NSString stringWithFormat:@"OT2 display layout test (no game running)\nWindow %.0f x %.0f pt | scale %.3f\nMetal drawable %.0f x %.0f px\nCanvas fills screen: %@ | Restart needed: %@\nYellow inner frame: authored 16:9 area",bounds.size.width,bounds.size.height,screen.nativeScale,layer.drawableSize.width,layer.drawableSize.height,fill?@"YES":@"NO",matches?@"NO":@"YES"];
    id<CAMetalDrawable> drawable=[layer nextDrawable];
    if(drawable) {
        MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor renderPassDescriptor];
        pass.colorAttachments[0].texture=drawable.texture;pass.colorAttachments[0].loadAction=MTLLoadActionClear;
        pass.colorAttachments[0].storeAction=MTLStoreActionStore;pass.colorAttachments[0].clearColor=MTLClearColorMake(0.02,0.32,0.36,1);
        id<MTLCommandBuffer> cb=[queue commandBuffer];id<MTLRenderCommandEncoder> encoder=[cb renderCommandEncoderWithDescriptor:pass];
        [encoder endEncoding];[cb presentDrawable:drawable];[cb commit];
    }
}
void front_ios_boot(void) {
    NSCAssert(getenv("DM_CAMERA_ASPECT") && getenv("DM_ROMFS_OVERLAY"),@"automatic setup must run before boot");
    sample_display();
    [NSTimer scheduledTimerWithTimeInterval:1 repeats:YES block:^(NSTimer *t){sample_display();}];
}
@interface SceneDelegate : UIResponder <UIWindowSceneDelegate>
@property UIWindow *window;
@end
@implementation SceneDelegate
- (void)scene:(UIScene*)scene willConnectToSession:(UISceneSession*)session options:(UISceneConnectionOptions*)options {
    setenv("DM_TEMP",NSTemporaryDirectory().UTF8String,1);setenv("DM_DISPLAY_AUTO","1",1);
    self.window=[[UIWindow alloc] initWithWindowScene:(UIWindowScene*)scene];
    self.window.rootViewController=front_ios_root();[self.window makeKeyAndVisible];
}
@end
@interface AppDelegate : UIResponder <UIApplicationDelegate>
@end
@implementation AppDelegate
@end
int main(int argc,char **argv) { @autoreleasepool { return UIApplicationMain(argc,argv,nil,NSStringFromClass(AppDelegate.class)); } }
