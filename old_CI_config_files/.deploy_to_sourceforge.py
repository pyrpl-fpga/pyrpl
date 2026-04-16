import sys
import os
from pyrpl import sshshell, __version__


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python .deploy_to_sourceforge.py file1 [file2] ...")

    pw = os.environ["PYPI_PSW"]
    ssh = sshshell.SshShell(
        hostname="frs.sourceforge.net", user="lneuhaus", password=pw, shell=False
    )
    for filename in sys.argv[1:]:
        for destpath in [
            "/home/frs/project/pyrpl/",
            f"/home/frs/project/pyrpl/{__version__}/",
        ]:
            print(f"Uploading file '{filename}' to '{destpath}' on sourceforge...")
            try:
                ssh.scp.put(filename, destpath)
            except BaseException as e:
                print(
                    f"Upload of file '{filename}' to '{destpath}' to sourceforge failed: {e}!"
                )
                ssh = sshshell.SshShell(
                    hostname="frs.sourceforge.net",
                    user="lneuhaus",
                    password=pw,
                    shell=False,
                )
            else:
                print(f"Finished upload of file '{filename}' to '{destpath}' on sourceforge!")
