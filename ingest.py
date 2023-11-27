from os import path

if not path.exists('data'):
  import subprocess
  subprocess.run(['fetch-data.sh'])


