import subprocess
import sys
import os

PYTHON = "D:\\python.exe"
PIPELINE = "E:\\shorts_pipeline\\pipeline.py"
MERGE    = "E:\\shorts_pipeline\\merge_fixed.py"

print("=== Run All: Starting Pipeline ===")

# Step 1: pipeline.py
print("\n[1/2] pipeline.py chal raha hai...")
result1 = subprocess.run([PYTHON, PIPELINE], capture_output=False)

if result1.returncode != 0:
    print("✗ pipeline.py fail ho gayi!")
    sys.exit(1)

print("\n[2/2] merge_fixed.py chal raha hai...")
result2 = subprocess.run([PYTHON, MERGE], capture_output=False)

if result2.returncode != 0:
    print("✗ merge_fixed.py fail ho gayi!")
    sys.exit(1)

print("\n✓ Run All complete! Video ready hai.")
print("\n[3/3] upload.py chal raha hai...")
result3 = subprocess.run([PYTHON, r"E:\shorts_pipeline\upload.py"], capture_output=False)

if result3.returncode != 0:
    print("✗ upload.py fail ho gayi!")
    sys.exit(1)

print("\n✓ Poori pipeline complete! Video YouTube pe upload ho gayi!")