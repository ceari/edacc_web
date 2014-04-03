import os, subprocess, sys

for filename in os.listdir("."):
    if filename.endswith('.zip'):
        subprocess.call(['unzip', '-q', filename, '-d', filename[:-4]])

for dirname, dirnames, filenames in os.walk("."):
    if not ('code' in dirnames and 'build.sh' in filenames): continue

    print "Executing", os.path.join(dirname, 'build.sh')

    for f in filenames:
        subprocess.call(['chmod', '+x', os.path.join(dirname, f)])

    proc = subprocess.Popen(['./build.sh'], shell=True, cwd=dirname, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = proc.communicate()

    print "Compilation ended with exit code", proc.returncode

    if proc.returncode != 0 or "error" in stdout.lower() or "error" in stderr.lower():
        print "Standard out:\n", stdout
        print "Standard error:\n", stderr
        print "Submitter email: ", open(dirname[2:32+2] + '.author', 'r').read()
    else:
        print "Compilation successful!"
    print "==============================\n\n"
