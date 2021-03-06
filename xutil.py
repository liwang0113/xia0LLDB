 #  ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ 
 # |______|______|______|______|______|______|______|______|______|______|______|______|______|______|______|______|______| 
 #        _        ___  _      _      _____  ____   
 #       (_)      / _ \| |    | |    |  __ \|  _ \  
 #  __  ___  __ _| | | | |    | |    | |  | | |_) | 
 #  \ \/ / |/ _` | | | | |    | |    | |  | |  _ <  
 #   >  <| | (_| | |_| | |____| |____| |__| | |_) | 
 #  /_/\_\_|\__,_|\___/|______|______|_____/|____/                                                                                                                   
 #  ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ ______ 
 # |______|______|______|______|______|______|______|______|______|______|______|______|______|______|______|______|______|

import lldb
import os
import shlex
import optparse
import json
import re

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand(
    'command script add -f xutil.handle_command xutil -h "[usage] xutil [options] args"')
    # print('========')
    # print('[xutil]: some util tool for debug, this command is flexable and some options maybe remove future')
    # print('\txutil [-b addr, -s module, -l dylib]')
    # print('\tmore usage, try "xutil -h"')
                    
def handle_command(debugger, command, exe_ctx, result, internal_dict):
    command_args = shlex.split(command, posix=False)
    parser = generate_option_parser()
    try:
        (options, args) = parser.parse_args(command_args)
    except:
        result.SetError(parser.usage)
        return
        
    target = exe_ctx.target
    thread = exe_ctx.thread
    
    if not args:
        ret = "[usage] xutil test"
    elif str(args[0]) in "test":
        ret = hook(debugger)
        result.AppendMessage(str(ret))
        return

    if options.kAntiDebug:
        ret = killAntiDebug(debugger)
        result.AppendMessage(str('kill antiDebug:')+str(ret))
        # lldb.debugger.HandleCommand ('re write %lx 0' % (int(ret), ))
        return
    
    if options.mainModuleAddress:
        setBreakpointAtMainImage(debugger, str(options.mainModuleAddress))
        return
        
    if options.sildeModule:
        ret = getBaseAddressFromModule(debugger, options.sildeModule)
        result.AppendMessage(str(ret))
        return
        
    if options.loadModule:
        ret = mload(debugger, str(options.loadModule))
        result.AppendMessage(str(ret))
        return

    if options.testarg:
        ret = test(debugger, options.testarg)
        result.AppendMessage(str(ret))
        return
            
    result.AppendMessage(str('nothing.'))
    return 


def attrStr(msg, color='black'):      
    clr = {
    'cyan' : '\033[36m',
    'grey' : '\033[2m',
    'blink' : '\033[5m',
    'redd' : '\033[41m',
    'greend' : '\033[42m',
    'yellowd' : '\033[43m',
    'pinkd' : '\033[45m',
    'cyand' : '\033[46m',
    'greyd' : '\033[100m',
    'blued' : '\033[44m',
    'whiteb' : '\033[7m',
    'pink' : '\033[95m',
    'blue' : '\033[94m',
    'green' : '\033[92m',
    'yellow' : '\x1b\x5b33m',
    'red' : '\033[91m',
    'bold' : '\033[1m',
    'underline' : '\033[4m'
    }[color]
    return clr + msg + ('\x1b\x5b39m' if clr == 'yellow' else '\033[0m')

def setBreakpointAtMainImage(debugger, address):    
    command_script = r'''
    uint32_t count = (uint32_t)_dyld_image_count();
    NSMutableString* retStr = [NSMutableString string];
    int idx = 0;
    NSString* image_name = @"";
    const char *path = (char *)[[[NSBundle mainBundle] executablePath] UTF8String];
    NSString* imagePath = [[NSString alloc] initWithUTF8String:path];
    
    for(int i = 0; i < count; i++){
        const char* imageName = (const char*)_dyld_get_image_name(i);
        NSString* imageNameStr = [[NSString alloc] initWithUTF8String:imageName];
        if([imageNameStr isEqualToString:imagePath]){
            idx = i;
            image_name = imageNameStr;
            break;
        }
    }
    uintptr_t slide =  (uintptr_t)_dyld_get_image_vmaddr_slide(idx);
    NSString *slideStr = [@(slide) stringValue];
    [retStr appendString:image_name];
    [retStr appendString:@"#"];
    [retStr appendString:slideStr];

    slideStr
    '''
    slide = exeScript(debugger, command_script)
    debugger.HandleCommand('br set -a "%s+%s"' % (slide, str(address)))
    
    
def getBaseAddressFromModule(debugger, moduleName):
    command_script = 'NSString* moduleName = @"' + moduleName + '";' 
    command_script += r'''
    NSMutableString* retStr = [NSMutableString string];
    
    uint32_t count = (uint32_t)_dyld_image_count();
    for(uint32_t i = 0; i < count; i++){
        char* curModuleName_cstr = (char*)_dyld_get_image_name(i);
        long slide = (long)_dyld_get_image_vmaddr_slide(i);
        uintptr_t baseAddr = (uintptr_t)_dyld_get_image_header(i);
        NSString* curModuleName = @(curModuleName_cstr);
        if([curModuleName containsString:moduleName]) {
            [retStr appendString:@"Module Path : "];
            [retStr appendString:@(curModuleName_cstr)];
            [retStr appendString:@"\nModule Silde: "];
            [retStr appendString:(id)[@(slide) stringValue]];
            [retStr appendString:@"\nModule base : "];
            [retStr appendString:(id)[@(baseAddr) stringValue]];
        }
    }
    retStr
    '''
    retStr = exeScript(debugger, command_script)
    return hexIntInStr(retStr)

def printIvarsOfObject(debugger, address):
    command_script = 'id xobject = (id)' + address + ';' 
    command_script += r'''
    NSMutableString* retStr = [NSMutableString string];
    const char* name;
    unsigned int count;
    struct objc_property **properties = (struct objc_property**)class_copyPropertyList((Class)object_getClass(xobject), &count);
    for(int i=0;i<count;i++){
        [retStr appendString:@"one"];
        name = (const char*)property_getName(properties[i]);
    }
    // retStr = [(NSObject*)xobject performSelector:(SEL)NSSelectorFromString(@"_ivarDescription")];
    //retStr = objc_msgsend(xobject, (SEL)NSSelectorFromString(@"_ivarDescription"));
    name
    '''
    retStr = exeScript(debugger, command_script)
    return retStr

def mload(debugger, modulePath):
    command_script = 'const char* module = "' + modulePath + '";' 
    command_script += r'''
    void *handle = (void *)dlopen(module, 2); 
    id retVal = handle ? @"Success" : @"fail"; 
    retVal
    '''
    retStr = exeScript(debugger, command_script)
    return retStr

def test(debugger, testarg):
    command_script = '@import Foundation;' 
    command_script += r'''
    id bundle = objc_msgSend((Class)objc_getClass("UIPasteboard"), @selector(generalPasteboard));
    id exePath = objc_msgSend((id)bundle, @selector(setString:), @"test123123");
    //[[UIPasteboard generalPasteboard] setString:@"123test"];
    
    "success"
    '''
    retStr = exeScript(debugger, command_script)
    return retStr
    pass

def getInfoByAddress(debugger, address):
    command_script = 'void * targetAddr = (void*)' + testarg + ';' 
    command_script += r'''
    NSMutableString* retStr = [NSMutableString string];

    typedef struct dl_info {
        const char      *dli_fname;     /* Pathname of shared object */
        void            *dli_fbase;     /* Base address of shared object */
        const char      *dli_sname;     /* Name of nearest symbol */
        void            *dli_saddr;     /* Address of nearest symbol */
    } Dl_info;

    Dl_info dl_info;

    dladdr(targetAddr, &dl_info);

    char* module_path = (char*)dl_info.dli_fname;

    [retStr appendString:@(module_path)];

    retStr
    '''
    retStr = exeScript(debugger, command_script)
    return retStr
    
def hook(debugger):
    command_script = ''
    command_script += r'''
    @import Foundation;
    @import ObjectiveC;
    
    NSString* hookLog = @"";
        
    
    Class clz = (Class)objc_getClass("ViewController");
    SEL originalSelector = NSSelectorFromString(@"onClick:");
    SEL hookSelector = NSSelectorFromString(@"imageFromColor:");
    SEL swizzledSelector = NSSelectorFromString([NSString stringWithFormat:@"_xia0_swizzle_%x_%@", arc4random(), NSStringFromSelector(originalSelector)]);
        
    Method originalMethod = class_getInstanceMethod(clz, originalSelector);
    Method hookMethod = class_getInstanceMethod(clz, hookSelector);
    if (!originalMethod) {
        hookLog = @"NULL originalMethod";
    }
    
   method_setImplementation(originalMethod, method_getImplementation(hookMethod));
    //class_addMethod(class, swizzledSelector, xblock, method_getTypeEncoding(originalMethod));
    //Method newMethod = class_getInstanceMethod(clz, swizzledSelector);
    //method_exchangeImplementations(originalMethod, newMethod);
    hookLog = @"Success";
    
    hookLog
    '''
    retStr = exeScript(debugger, command_script)
    return retStr
    
def showAllUserDefaults(debugger):
    command_script = r'''
    NSArray *keys = [[[NSUserDefaults standardUserDefaults] dictionaryRepresentation] allKeys];
    NSArray *values = [[[NSUserDefaults standardUserDefaults] dictionaryRepresentation] allValues];
    NSMutableString* retStr = [NSMutableString string];
    
    for(int i = 0; i < 1; i++){
       [retStr appendString:keys[i]];
       [retStr appendString:@"------->"];
       [retStr appendString:values[i]];
       [retStr appendString:@"\n"];
    }
    retStr
    '''
    return exeScript(debugger, command_script)

  
def hexIntInStr(needHexStr):

    def handler(reobj):
        intvalueStr = reobj.group(0)
        
        r = hex(int(intvalueStr))
        return r

    pattern = '(?<=\s)[0-9]{1,}(?=\s)'

    return re.sub(pattern, handler, needHexStr, flags = 0)  

def exeScript(debugger,command_script):
    res = lldb.SBCommandReturnObject()
    interpreter = debugger.GetCommandInterpreter()
    interpreter.HandleCommand('exp -lobjc -O -- ' + command_script, res)

    if not res.HasResult():
        # something error
        return res.GetError()
            
    response = res.GetOutput()
    return response

def generateOptions():
    expr_options = lldb.SBExpressionOptions()
    expr_options.SetUnwindOnError(True)
    expr_options.SetLanguage (lldb.eLanguageTypeObjC_plus_plus)
    expr_options.SetCoerceResultToId(False)
    return expr_options

def generate_option_parser():
    usage = "usage: xutil [options] args"
    parser = optparse.OptionParser(usage=usage, prog="lookup")

    parser.add_option("-b", "--breakpointAtMainModule",
                        action="store",
                        default=None,
                        dest="mainModuleAddress",
                        help="set a breakpoint at main module of given address")
                        
    parser.add_option("-s", "--slide",
                        action="store",
                        default=None,
                        dest="sildeModule",
                        help="get slide of given module")

    parser.add_option("-l", "--load",
                    action="store",
                    default=None,
                    dest="loadModule",
                    help="load a macho file")

    parser.add_option("-k", "--killAntiDebug",
                action="store_true",
                default=None,
                dest='kAntiDebug',
                help="bypass anti debug")

    parser.add_option("-t", "--test",
                action="store",
                default=None,
                dest="testarg",
                help="do some testing")
                

    return parser
