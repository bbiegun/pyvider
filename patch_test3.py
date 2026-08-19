with open("tests/tfprotov6/handlers/test_deferral.py", "r") as f:
    content = f.read()

content = content.replace("hub.clear()", "# hub is managed by other fixtures or doesn't need clear")

with open("tests/tfprotov6/handlers/test_deferral.py", "w") as f:
    f.write(content)
