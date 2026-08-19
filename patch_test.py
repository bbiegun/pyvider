with open("tests/tfprotov6/handlers/test_deferral.py", "r") as f:
    content = f.read()

content = content.replace("        state_class = dict\n        private_state_class = None", "        config_class = dict\n        state_class = dict\n        private_state_class = None")

with open("tests/tfprotov6/handlers/test_deferral.py", "w") as f:
    f.write(content)
