import os

try:
    user_dir = os.environ["PYRPL_USER_DIR"]
except KeyError:
    user_dir = os.path.join(os.path.expanduser("~"), "pyrpl_user_dir")

user_config_dir = os.path.join(user_dir, "config")
user_curve_dir = os.path.join(user_dir, "curve")
user_lockbox_dir = os.path.join(user_dir, "lockbox")
default_config_dir = os.path.join(os.path.dirname(__file__), "config")

# create dirs if necessary
for path in [user_dir, user_config_dir, user_curve_dir, user_lockbox_dir]:
    if not os.path.isdir(path):
        os.mkdir(path)  # pragma: no cover
