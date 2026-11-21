# Witness target for l9_ci/rulesets/semgrep/rule-overlaps.yaml: every form of a
# subprocess call with shell=True. Never imported or executed.
import subprocess

user = input()

subprocess.run(user, shell=True)
subprocess.call(user, shell=True, cwd="/")
subprocess.Popen(user, shell=True)
subprocess.check_call(user, shell=True)
subprocess.check_output(user, shell=True, text=True)
subprocess.run(
    user,
    shell=True,
    capture_output=True,
)
subprocess.run("echo literal", shell=True)
subprocess.run([user], shell=False)
