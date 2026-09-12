#!/usr/bin/env python3
"""Build and test the phone scheme, including its watchOS companion products."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import platform
import subprocess

IOS = Path(__file__).resolve().parents[1]


def run(*arguments):
    subprocess.run(list(map(str, arguments)), check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', required=True, help='iPhone simulator UUID from simctl list devices available')
    parser.add_argument('--without-icon', action='store_true', help='Skip icon catalogs for a diagnostic build; does not replace installing watchOS in Xcode')
    args = parser.parse_args()
    output = IOS / 'TestResults' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True)
    destination = 'platform=iOS Simulator,id=' + args.device + ',arch=' + platform.machine()
    # A global -sdk iphonesimulator overrides the Watch target's SDK too.
    # The scheme lets Xcode build each embedded product for its own platform.
    build = ['xcodebuild', '-project', IOS / 'E36OBD.xcodeproj', '-scheme', 'E36OBD',
             '-configuration', 'Debug', '-destination', destination,
             '-derivedDataPath', output / 'Build', 'CODE_SIGNING_ALLOWED=YES', 'CODE_SIGN_IDENTITY=-']
    if args.without_icon:
        print('Diagnostic build omits icon catalogs; asset compilation is not validated.', flush=True)
        build.append('EXCLUDED_SOURCE_FILE_NAMES=Assets.xcassets')
    run(*build, 'build-for-testing')
    test_runs = list((output / 'Build/Build/Products').glob('*.xctestrun'))
    if len(test_runs) != 1:
        raise RuntimeError('Expected one generated xctestrun; found ' + str(test_runs))
    run('xcrun', 'simctl', 'bootstatus', args.device, '-b')
    run('xcodebuild', 'test-without-building', '-xctestrun', test_runs[0],
        '-destination', destination, '-parallel-testing-enabled', 'NO',
        '-resultBundlePath', output / 'Tests.xcresult')
    print('Results and screenshots:', output / 'Tests.xcresult')


if __name__ == '__main__':
    main()
