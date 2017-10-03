import argparse
import ConfigParser
import os
import sys
from subprocess import Popen
import errno
import json
import FioResultDecoder
import platform
import ResultData
import FioCompare

# Shamelessly copied from stackoverflow
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def run_command(cmd):
    print("  running cmd '{}'".format(cmd))
    devnull = open('/dev/null')
    p = Popen(cmd.split(' '), stdout=devnull, stderr=devnull)
    p.wait()
    devnull.close()
    if p.returncode == 0:
        return
    print("Command '{}' failed to run".format(cmd))
    sys.exit(1)

def run_test(config, result_data, section, test):
    testname = test[:-4]
    compare = result_data.load_last(testname, section)
    print("Running {}".format(testname))
    if config.has_option(section, 'mkfs'):
        run_command(config.get(section, 'mkfs'))
    if config.has_option(section, 'mount'):
        run_command(config.get(section, 'mount'))
    cmd = "fio --output-format=json --output=results/{}.json".format(testname)
    cmd += " --directory {}".format(config.get(section, 'directory'))
    cmd += " {}".format("tests/" + test)
    run_command(cmd)
    if config.has_option(section, 'mount'):
        run_command("umount {}".format(config.get(section, 'directory')))
    json_data = open("results/{}.json".format(testname))
    data = json.load(json_data, cls=FioResultDecoder.FioResultDecoder)
    data['global']['config'] = section
    data['global']['kernel'] = platform.release()
    result_data.insert_result(data)
    if compare is None:
        return 0
    return FioCompare.compare_fiodata(compare, data)

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, default='default',
                    help="Configuration to use to run the tests")

args = parser.parse_args()
config = ConfigParser.ConfigParser()
config.readfp(open('local.cfg'))

failed_tests = []

if not config.has_section(args.config):
    print("No section '{}' in local.cfg".format(args.config))
    sys.exit(1)

if not config.has_option(args.config, "directory"):
    print("Must specify a directory option in section {}".format(args.config))
    sys.exit(1)

result_data = ResultData.ResultData("fsperf-results.db")
mkdir_p("results/")

tests = []
for (dirpath, dirnames, filenames) in os.walk("tests/"):
    tests.extend(filenames)

for t in tests:
    if t.endswith(".fio"):
        ret = run_test(config, result_data, args.config, t)
        if ret != 0:
            failed_tests.append(t)

if len(failed_tests) > 0:
    print("Failed {} tests: {}".format(len(failed_tests),
          " ".join(failed_tests)))
    sys.exit(1)
print("Passed all tests")