# Example script to bundle files into a single prompt-friendly text
import os

package_dir = "/Users/harrisgordon/Documents/Development/Python/edge-nhl"
output = []

for root, _, files in os.walk(package_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                output.append(f"# --- File: {path} ---\n{f.read()}\n\n")

with open("combined_code.txt", "w") as f:
    f.write("".join(output))