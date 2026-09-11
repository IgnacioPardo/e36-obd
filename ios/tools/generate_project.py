#!/usr/bin/env python3
"""Regenerate the checked-in Xcode project using only the Python standard library."""
import hashlib
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
objects = {}


def ident(name):
    return hashlib.sha1(name.encode()).hexdigest()[:24].upper()


def add(name, value):
    key = ident(name)
    objects[key] = value
    return key


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def render(value, level=0):
    if isinstance(value, dict):
        return '{\n' + ''.join('\t' * (level + 1) + quote(key) + ' = ' + render(val, level + 1) + ';\n' for key, val in value.items()) + '\t' * level + '}'
    if isinstance(value, list):
        return '(\n' + ''.join('\t' * (level + 1) + render(val, level + 1) + ',\n' for val in value) + '\t' * level + ')'
    return quote(value)


package = add('core-package', dict(isa='XCLocalSwiftPackageReference', relativePath='Core'))
product_refs, groups, targets = [], [], []
shared_files = []
for path in sorted((ROOT / 'WidgetShared').glob('*.swift')):
    shared_files.append(add(str(path.relative_to(ROOT)), dict(isa='PBXFileReference', lastKnownFileType='sourcecode.swift', path=path.name, sourceTree='<group>')))
for name, folder, product_type, extension in [
    ('E36OBD', 'E36OBD', 'com.apple.product-type.application', 'app'),
    ('E36OBDWidgets', 'E36OBDWidgets', 'com.apple.product-type.app-extension', 'appex'),
    ('E36OBDTests', 'E36OBDTests', 'com.apple.product-type.bundle.unit-test', 'xctest'),
    ('E36OBDUITests', 'E36OBDUITests', 'com.apple.product-type.bundle.ui-testing', 'xctest'),
]:
    files, sources, resources, frameworks, products = [], [], [], [], []
    for path in sorted(p for p in (ROOT / folder).iterdir() if p.suffix in ['.swift', '.metal']):
        ref = add(str(path.relative_to(ROOT)), dict(isa='PBXFileReference', lastKnownFileType='sourcecode.metal' if path.suffix == '.metal' else 'sourcecode.swift', path=path.name, sourceTree='<group>'))
        files.append(ref)
        sources.append(add(str(path.relative_to(ROOT)) + ':build', dict(isa='PBXBuildFile', fileRef=ref)))
    if name in ['E36OBD', 'E36OBDWidgets']:
        sources.extend(add(name + ':shared:' + ref, dict(isa='PBXBuildFile', fileRef=ref)) for ref in shared_files)
        files.append(add(name + ':entitlements', dict(isa='PBXFileReference', lastKnownFileType='text.plist.entitlements', path=name + '.entitlements', sourceTree='<group>')))
    if name == 'E36OBD':
        for filename, kind in [('Assets.xcassets', 'folder.assetcatalog'), ('VehicleScene', 'folder'), ('alert.wav', 'audio.wav'), ('Info.plist', 'text.plist.xml')]:
            ref = add(filename, dict(isa='PBXFileReference', lastKnownFileType=kind, path=filename, sourceTree='<group>'))
            files.append(ref)
            if filename != 'Info.plist':
                resources.append(add(filename + ':build', dict(isa='PBXBuildFile', fileRef=ref)))
    elif name == 'E36OBDWidgets':
        files.append(add(name + ':info', dict(isa='PBXFileReference', lastKnownFileType='text.plist.xml', path='Info.plist', sourceTree='<group>')))
    if name != 'E36OBDUITests':
        dependency = add(name + ':core', dict(isa='XCSwiftPackageProductDependency', package=package, productName='E36Core'))
        products.append(dependency)
        frameworks.append(add(name + ':core-build', dict(isa='PBXBuildFile', productRef=dependency)))
    groups.append(add(name + ':group', dict(isa='PBXGroup', children=files, path=folder, sourceTree='<group>')))
    file_type = {'app': 'wrapper.application', 'appex': 'wrapper.app-extension', 'xctest': 'wrapper.cfbundle'}[extension]
    product = add(name + ':product', dict(isa='PBXFileReference', explicitFileType=file_type, includeInIndex='0', path=name + '.' + extension, sourceTree='BUILT_PRODUCTS_DIR'))
    product_refs.append(product)
    phases = []
    for kind, entries in [('Sources', sources), ('Frameworks', frameworks), ('Resources', resources)]:
        phases.append(add(name + ':' + kind, dict(isa='PBX' + kind + 'BuildPhase', buildActionMask='2147483647', files=entries, runOnlyForDeploymentPostprocessing='0')))
    if name == 'E36OBD':
        embedded = add('widget:embed', dict(isa='PBXBuildFile', fileRef=ident('E36OBDWidgets:product'), settings={'ATTRIBUTES': ['RemoveHeadersOnCopy']}))
        phases.append(add('widget:copy', dict(isa='PBXCopyFilesBuildPhase', buildActionMask='2147483647', dstPath='', dstSubfolderSpec='13', files=[embedded], name='Embed App Extensions', runOnlyForDeploymentPostprocessing='0')))
    configurations = []
    for mode in ['Debug', 'Release']:
        settings = dict(PRODUCT_NAME='$(TARGET_NAME)', PRODUCT_BUNDLE_IDENTIFIER='com.ignaciopardo.' + name.lower(),
                        CODE_SIGN_STYLE='Automatic', SWIFT_VERSION='6.0', IPHONEOS_DEPLOYMENT_TARGET='18.0',
                        TARGETED_DEVICE_FAMILY='1', GENERATE_INFOPLIST_FILE='YES',
                        LD_RUNPATH_SEARCH_PATHS=['$(inherited)', '@executable_path/Frameworks', '@loader_path/Frameworks'])
        if name == 'E36OBD':
            settings.update(INFOPLIST_FILE='E36OBD/Info.plist', GENERATE_INFOPLIST_FILE='NO',
                            CODE_SIGN_ENTITLEMENTS='E36OBD/E36OBD.entitlements',
                            ASSETCATALOG_COMPILER_APPICON_NAME='AppIcon', ENABLE_PREVIEWS='YES',
                            SUPPORTS_MACCATALYST='NO', SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD='NO',
                            INFOPLIST_KEY_UIApplicationSceneManifest_Generation='YES')
        elif name == 'E36OBDWidgets':
            settings.update(PRODUCT_BUNDLE_IDENTIFIER='com.ignaciopardo.e36obd.widgets',
                            INFOPLIST_FILE='E36OBDWidgets/Info.plist', GENERATE_INFOPLIST_FILE='NO',
                            CODE_SIGN_ENTITLEMENTS='E36OBDWidgets/E36OBDWidgets.entitlements',
                            APPLICATION_EXTENSION_API_ONLY='YES', SKIP_INSTALL='YES', ENABLE_PREVIEWS='YES',
                            LD_RUNPATH_SEARCH_PATHS=['$(inherited)', '@executable_path/Frameworks', '@executable_path/../../Frameworks'])
        elif name == 'E36OBDTests':
            settings.update(TEST_HOST='$(BUILT_PRODUCTS_DIR)/E36OBD.app/E36OBD', BUNDLE_LOADER='$(TEST_HOST)')
        else:
            settings.update(TEST_TARGET_NAME='E36OBD')
        configurations.append(add(name + ':' + mode, dict(isa='XCBuildConfiguration', buildSettings=settings, name=mode)))
    configuration_list = add(name + ':configurations', dict(isa='XCConfigurationList', buildConfigurations=configurations, defaultConfigurationIsVisible='0', defaultConfigurationName='Release'))
    dependencies = []
    if name in ['E36OBDTests', 'E36OBDUITests']:
        proxy = add(name + ':proxy', dict(isa='PBXContainerItemProxy', containerPortal=ident('project'), proxyType='1', remoteGlobalIDString=ident('E36OBD:target'), remoteInfo='E36OBD'))
        dependencies.append(add(name + ':dependency', dict(isa='PBXTargetDependency', target=ident('E36OBD:target'), targetProxy=proxy)))
    elif name == 'E36OBD':
        proxy = add('widget:proxy', dict(isa='PBXContainerItemProxy', containerPortal=ident('project'), proxyType='1', remoteGlobalIDString=ident('E36OBDWidgets:target'), remoteInfo='E36OBDWidgets'))
        dependencies.append(add('widget:dependency', dict(isa='PBXTargetDependency', target=ident('E36OBDWidgets:target'), targetProxy=proxy)))
    targets.append(add(name + ':target', dict(isa='PBXNativeTarget', buildConfigurationList=configuration_list, buildPhases=phases,
        buildRules=[], dependencies=dependencies, name=name, packageProductDependencies=products, productName=name,
        productReference=product, productType=product_type)))

groups.append(add('widget-shared-group', dict(isa='PBXGroup', children=shared_files, path='WidgetShared', sourceTree='<group>')))
products_group = add('products-group', dict(isa='PBXGroup', children=product_refs, name='Products', sourceTree='<group>'))
main_group = add('main-group', dict(isa='PBXGroup', children=groups + [products_group], sourceTree='<group>'))
configs = []
for mode in ['Debug', 'Release']:
    settings = dict(SDKROOT='iphoneos', CLANG_ENABLE_MODULES='YES', CLANG_ENABLE_OBJC_ARC='YES',
                    SWIFT_STRICT_CONCURRENCY='complete', ENABLE_USER_SCRIPT_SANDBOXING='YES',
                    SWIFT_OPTIMIZATION_LEVEL='-Onone' if mode == 'Debug' else '-O',
                    DEBUG_INFORMATION_FORMAT='dwarf' if mode == 'Debug' else 'dwarf-with-dsym',
                    SWIFT_ACTIVE_COMPILATION_CONDITIONS='DEBUG' if mode == 'Debug' else '',
                    ENABLE_TESTABILITY='YES' if mode == 'Debug' else 'NO',
                    GCC_PREPROCESSOR_DEFINITIONS=['DEBUG=1', '$(inherited)'] if mode == 'Debug' else ['$(inherited)'])
    configs.append(add('project:' + mode, dict(isa='XCBuildConfiguration', buildSettings=settings, name=mode)))
project_config = add('project:configs', dict(isa='XCConfigurationList', buildConfigurations=configs, defaultConfigurationIsVisible='0', defaultConfigurationName='Release'))
add('project', dict(isa='PBXProject', attributes=dict(BuildIndependentTargetsInParallel='YES', LastUpgradeCheck='2620',
    TargetAttributes={ident(name + ':target'): dict(CreatedOnToolsVersion='26.2', SystemCapabilities={'com.apple.ApplicationGroups.iOS': {'enabled': '1'}}) for name in ['E36OBD', 'E36OBDWidgets']}),
    buildConfigurationList=project_config, compatibilityVersion='Xcode 14.0', developmentRegion='es', hasScannedForEncodings='0',
    knownRegions=['es', 'en', 'Base'], mainGroup=main_group, packageReferences=[package], productRefGroup=products_group,
    projectDirPath='', projectRoot='', targets=targets))

project = ROOT / 'E36OBD.xcodeproj'
project.mkdir(exist_ok=True)
(project / 'project.pbxproj').write_text('// !$*UTF8*$!\n' + render(dict(archiveVersion='1', classes={}, objectVersion='56', objects=objects, rootObject=ident('project'))) + '\n')
schemes = project / 'xcshareddata' / 'xcschemes'
schemes.mkdir(parents=True, exist_ok=True)


def reference(name, extension):
    return f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{ident(name + ":target")}" BuildableName="{name}.{extension}" BlueprintName="{name}" ReferencedContainer="container:E36OBD.xcodeproj"/>'


for demo in [False, True]:
    name = 'E36OBD Demo' if demo else 'E36OBD'
    scheme = f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="2620" version="1.3">
 <BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>
  <BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES">{reference('E36OBD','app')}</BuildActionEntry>
 </BuildActionEntries></BuildAction>
 <TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="NO">
  <Testables><TestableReference skipped="NO">{reference('E36OBDTests','xctest')}</TestableReference><TestableReference skipped="NO">{reference('E36OBDUITests','xctest')}</TestableReference></Testables>
  <CommandLineArguments><CommandLineArgument argument="--demo" isEnabled="YES"/></CommandLineArguments>
 </TestAction>
 <LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="NO">
  <BuildableProductRunnable runnableDebuggingMode="0">{reference('E36OBD','app')}</BuildableProductRunnable>
  <CommandLineArguments><CommandLineArgument argument="--demo" isEnabled="{'YES' if demo else 'NO'}"/></CommandLineArguments>
 </LaunchAction>
 <ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"><BuildableProductRunnable runnableDebuggingMode="0">{reference('E36OBD','app')}</BuildableProductRunnable></ProfileAction>
 <AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
'''
    (schemes / (name + '.xcscheme')).write_text(scheme)
print(project)
