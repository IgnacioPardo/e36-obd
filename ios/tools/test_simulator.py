#!/usr/bin/env python3
"""Build all targets and run XCTest on an explicitly selected installed simulator."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import platform
import plistlib
import subprocess

IOS = Path(__file__).resolve().parents[1]


def run(*arguments):
    subprocess.run(list(map(str, arguments)), check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, help='Simulator UUID from xcrun simctl list devices available')
    parser.add_argument('--without-icon', action='store_true', help='Skip ONLY the icon catalog when actool requires a missing SDK-matched runtime')
    args = parser.parse_args()
    output = IOS / 'TestResults' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True)
    build = ['xcodebuild', '-project', IOS / 'E36OBD.xcodeproj', '-alltargets', '-configuration', 'Debug',
             '-sdk', 'iphonesimulator', 'CODE_SIGNING_ALLOWED=YES', 'CODE_SIGN_IDENTITY=-', 'ARCHS=' + platform.machine(),
             'SYMROOT=' + str(output / 'Build')]
    if args.without_icon:
        print('Test build omits the app icon. This does not validate asset compilation.', flush=True)
        build.append('EXCLUDED_SOURCE_FILE_NAMES=Assets.xcassets')
    run(*build, 'build')
    products = output / 'Build/Debug-iphonesimulator'
    app, runner = products / 'E36OBD.app', products / 'E36OBDUITests-Runner.app'
    runner_id = plistlib.loads((runner / 'Info.plist').read_bytes())['CFBundleIdentifier']
    targets = [
        dict(BlueprintName='E36OBDTests', ProductModuleName='E36OBDTests',
             TestBundlePath=str(app / 'PlugIns/E36OBDTests.xctest'), TestHostPath=str(app),
             IsAppHostedTestBundle=True, TestHostBundleIdentifier='com.ignaciopardo.e36obd',
             CommandLineArguments=['--demo', '--uitesting'], ParallelizationEnabled=False,
             TestingEnvironmentVariables={'DYLD_INSERT_LIBRARIES': '__PLATFORMS__/iPhoneSimulator.platform/Developer/usr/lib/libXCTestBundleInject.dylib'},
             DependentProductPaths=[str(app)]),
        dict(BlueprintName='E36OBDUITests', ProductModuleName='E36OBDUITests',
             TestBundlePath=str(runner / 'PlugIns/E36OBDUITests.xctest'), TestHostPath=str(runner),
             UITargetAppPath=str(app), IsUITestBundle=True, IsAppHostedTestBundle=False,
             TestHostBundleIdentifier=runner_id, UITargetAppBundleIdentifier='com.ignaciopardo.e36obd',
             DependentProductPaths=[str(app), str(runner)], ParallelizationEnabled=False,
             SystemAttachmentLifetime='keepAlways', UserAttachmentLifetime='keepAlways'),
    ]
    for target in targets:
        if not Path(target['TestBundlePath']).is_dir():
            raise RuntimeError('Missing test product: ' + target['TestBundlePath'])
    configuration = {'__xctestrun_metadata__': {'FormatVersion': 2}, 'TestConfigurations': [
        dict(Name='Local simulator', IsEnabled=True, TestTargets=targets)]}
    test_run = output / 'E36OBD.xctestrun'
    test_run.write_bytes(plistlib.dumps(configuration))
    run('xcrun', 'simctl', 'bootstatus', args.device, '-b')
    run('xcodebuild', 'test-without-building', '-xctestrun', test_run,
        '-destination', 'platform=iOS Simulator,id=' + args.device + ',arch=' + platform.machine(),
        '-parallel-testing-enabled', 'NO', '-resultBundlePath', output / 'Tests.xcresult')
    print('Results and screenshots:', output / 'Tests.xcresult')


if __name__ == '__main__':
    main()
