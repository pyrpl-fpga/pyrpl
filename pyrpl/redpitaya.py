###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

from . import redpitaya_client
from . import hardware_modules as rp
from .sshshell import SshShell
from .pyrpl_utils import (
    get_unique_name_list_from_class_list,
    update_with_typeconversion,
)
from .memory import MemoryTree
from .errors import ExpectedPyrplError
from .widgets.startup_widget import HostnameSelectorWidget

import logging
import os
import random
from time import sleep

from paramiko import SSHException
from scp import SCPException
from collections import OrderedDict

# input is the wrong function in python 2
try:
    raw_input
except NameError:  # Python 3
    raw_input = input

# default parameters for redpitaya object creation
defaultparameters = dict(
    hostname="",  #'192.168.1.100', # the ip or hostname of the board, '' triggers gui
    port=2222,  # port for PyRPL datacommunication
    sshport=22,  # port of ssh server - default 22
    user="root",
    password="root",
    delay=0.05,  # delay between ssh commands - console is too slow otherwise
    autostart=True,  # autostart the client?
    reloadserver=False,  # reinstall the server at startup if not necessary?
    reloadfpga="auto",  # reload the fpga binfile at startup? True/False/'auto'
    filename="fpga/red_pitaya.bin",  # default name of the binfile for the fpga
    dtbo_filename="fpga/red_pitaya.dtbo",  # default name of device tree file
    # name of the binfile on the server and in the device tree overlay file
    serverbinfilename="fpga.bit.bin",
    serverdtbofilename="fpga.dtbo",  # name of the device tree overlay file on the server
    serverdirname="//opt//pyrpl//",  # server directory for server app and bitfile
    leds_off=True,  # turn off all GPIO lets at startup (improves analog performance)
    frequency_correction=1.0,  # actual FPGA frequency is 125 MHz * frequency_correction
    timeout=1,  # timeout in seconds for ssh communication
    monitor_server_name="monitor_server",  # name of the server program on redpitaya
    silence_env=False,  # suppress all environment variables that may override the configuration?
    gui=True,  # show graphical user interface or work on command-line only?
)


class RedPitaya:
    cls_modules = (
        [rp.HK, rp.AMS, rp.Scope, rp.Sampler, rp.Asg0, rp.Asg1]
        + [rp.Pwm] * 2
        + [rp.Iq] * 3
        + [rp.Pid] * 3
        + [rp.Trig]
        + [rp.IIR]
    )

    def __init__(
        self,
        config=None,  # configfile is needed to store parameters. None simulates one
        **kwargs,
    ):
        """this class provides the basic interface to the redpitaya board

        The constructor installs and starts the communication interface on the RedPitaya
        at 'hostname' that allows remote control and readout

        'config' is the config file or MemoryTree of the config file. All keyword arguments
        may be specified in the branch 'redpitaya' of this config file. Alternatively,
        they can be overwritten by keyword arguments at the function call.

        'config=None' specifies that no persistent config file is saved on the disc.

        Possible keyword arguments and their defaults are:
            hostname='192.168.1.100', # the ip or hostname of the board
            port=2222,  # port for PyRPL datacommunication
            sshport=22,  # port of ssh server - default 22
            user='root',
            password='root',
            delay=0.05,  # delay between ssh commands - console is too slow otherwise
            autostart=True,  # autostart the client?
            reloadserver=False,  # reinstall the server at startup if not necessary?
            reloadfpga='auto',  # reload the fpga bitfile at startup? True/False/'auto'
            filename='fpga/red_pitaya.bin',  # name of the binfile for the fpga
            dtbo_filename='fpga/red_pitaya.dtbo', # name of device tree file
            # name of the binfile on the server and in the device tree overlay file
            serverbinfilename='fpga.bit.bin',
            serverdtbofilename='fpga.dtbo',  # name of the device tree overlay file on the server
            serverdirname = "//opt//pyrpl//",  # server directory for server app and bitfile
            leds_off=True,  # turn off all GPIO lets at startup (improves analog performance)
            frequency_correction=1.0,  # actual FPGA frequency is 125 MHz * frequency_correction
            timeout=3,  # timeout in seconds for ssh communication
            monitor_server_name='monitor_server',  # name of the server program on redpitaya
            # suppress all environment variables that may override the configuration?
            silence_env=False,
            gui=True  # show graphical user interface or work on command-line only?

        if you are experiencing problems, try to increase delay, or try
        logging.getLogger().setLevel(logging.DEBUG)"""
        self.logger = logging.getLogger(name=__name__)
        # self.license()
        # make or retrieve the config file
        if isinstance(config, MemoryTree):
            self.c = config
        else:
            self.c = MemoryTree(config)
        # get the parameters right (in order of increasing priority):
        # 1. defaults
        # 2. environment variables
        # 3. config file
        # 4. command line arguments
        # 5. (if missing information) request from GUI or command-line
        self.parameters = defaultparameters  # BEWARE: By not copying the
        # dictionary, defaultparameters are modified in the session (which
        # can be advantageous for instance with hostname in unit_tests)

        # get parameters from os.environment variables
        if not self.parameters["silence_env"]:
            for k in self.parameters.keys():
                if "REDPITAYA_" + k.upper() in os.environ:
                    newvalue = os.environ["REDPITAYA_" + k.upper()]
                    oldvalue = self.parameters[k]
                    self.parameters[k] = type(oldvalue)(newvalue)
                    if k == "password":  # do not show the password on the screen
                        oldvalue = "********"
                        newvalue = "********"
                    self.logger.debug(
                        "Variable %s with value %s overwritten "
                        "by environment variable REDPITAYA_%s "
                        "with value %s. Use argument "
                        "'silence_env=True' if this is not "
                        "desired!",
                        k,
                        oldvalue,
                        k.upper(),
                        newvalue,
                    )
        # settings from config file
        try:
            update_with_typeconversion(self.parameters, self.c._get_or_create("redpitaya")._data)
        except Exception as e:
            self.logger.warning(
                "An error occured during the loading of your "
                "Red Pitaya settings from the config file: %s",
                e,
            )
        # settings from class initialisation / command line
        update_with_typeconversion(self.parameters, kwargs)
        # get missing connection settings from gui/command line
        if self.parameters["hostname"] is None or self.parameters["hostname"] == "":
            gui = "gui" not in self.c._keys() or self.c.gui
            if gui:
                self.logger.info(
                    "Please choose the hostname of your Red Pitaya in the hostname selector window!"
                )
                startup_widget = HostnameSelectorWidget(config=self.parameters)
                hostname_kwds = startup_widget.get_kwds()
            else:
                hostname = raw_input("Enter hostname [192.168.1.100]: ")
                hostname = "192.168.1.100" if hostname == "" else hostname
                hostname_kwds = dict(hostname=hostname)
                if "sshport" not in kwargs:
                    sshport = raw_input("Enter sshport [22]: ")
                    sshport = 22 if sshport == "" else int(sshport)
                    hostname_kwds["sshport"] = sshport
                if "user" not in kwargs:
                    user = raw_input("Enter username [root]: ")
                    user = "root" if user == "" else user
                    hostname_kwds["user"] = user
                if "password" not in kwargs:
                    password = raw_input("Enter password [root]: ")
                    password = "root" if password == "" else password
                    hostname_kwds["password"] = password
            self.parameters.update(hostname_kwds)

        # optional: write configuration back to config file
        self.c["redpitaya"] = self.parameters

        # save default port definition for possible automatic port change
        self.parameters["defaultport"] = self.parameters["port"]
        # frequency_correction is accessed by child modules
        self.frequency_correction = self.parameters["frequency_correction"]
        # memorize whether server is running - nearly obsolete
        self._serverrunning = False
        self.client = None  # client class
        self._slaves = []  # slave interfaces to same redpitaya
        self.modules = OrderedDict()  # all submodules

        # provide option to simulate a RedPitaya
        if self.parameters["hostname"] in ["_FAKE_REDPITAYA_", "_FAKE_"]:
            self.startdummyclient()
            self.logger.warning(
                "Simulating RedPitaya because (hostname=="
                + self.parameters["hostname"]
                + "). Incomplete "
                "functionality possible. "
            )
            return
        elif self.parameters["hostname"] in ["_NONE_"]:
            self.modules = []
            self.logger.warning(
                "No RedPitaya created (hostname==" + self.parameters["hostname"] + ")."
                " No hardware modules are available. "
            )
            return
        # connect to the redpitaya board
        self.start_ssh()
        # start other stuff
        self.get_os_version()  # get os version for later use

        # Handle reloadfpga with auto option
        should_reload_fpga = self._should_reload_fpga()

        if should_reload_fpga:  # flash fpga
            self._update_fpga()
        if self.parameters["reloadserver"]:  # reinstall server app
            self.installserver()
        if self.parameters["autostart"]:  # start client
            self.start()
        self.logger.info(
            f"Successfully connected to Redpitaya with hostname {self.ssh.hostname}."
        )
        self.parent = self

    def _should_reload_fpga(self):
        """
        Determine if FPGA should be reloaded based on reloadfpga parameter.

        Returns:
            bool: True if FPGA should be reloaded, False otherwise
        """
        reloadfpga = self.parameters["reloadfpga"]

        # Handle True/False cases
        if reloadfpga is True or reloadfpga == "true" or reloadfpga == "True":
            self.logger.debug("reloadfpga=True: FPGA will be reloaded")
            return True
        elif reloadfpga is False or reloadfpga == "false" or reloadfpga == "False":
            self.logger.debug("reloadfpga=False: FPGA will not be reloaded")

        # Handle 'auto' case
        elif reloadfpga == "auto":
            self.logger.debug("reloadfpga='auto': checking if proper image is loaded")
            if self._is_correct_fpga_image_loaded():
                self.logger.info("Correct FPGA image detected, skipping reload")
                return False
            else:
                self.logger.info("Correct FPGA image not detected, will reload")
                return True
        else:
            self.logger.warning("Unknown reloadfpga value '%s', defaulting to auto", reloadfpga)
            return self._should_reload_fpga() if self.parameters["reloadfpga"] == "auto" else True

    def _is_correct_fpga_image_loaded(self):
        """
        Check if the correct FPGA image is currently loaded.

        Returns:
            bool: True if correct image is loaded, False otherwise
        """
        try:
            # Check /tmp/loaded_fpga.inf to see what's currently loaded
            self.ssh.ask()  # clear buffer
            result = self.ssh.ask("cat /tmp/loaded_fpga.inf")
            self.logger.debug("Current FPGA image: %s", result)

            # If it says 'pyrpl', we consider it correct
            if "pyrpl" in result.lower():
                self.logger.debug("FPGA already loaded with PyRPL image")
                return True
            else:
                self.logger.debug("FPGA loaded with different image: %s", result)
                return False

        except (AttributeError, OSError, RuntimeError) as e:
            self.logger.warning("Could not determine FPGA image status: %s", e)
            # If we can't check, assume we need to reload
            return False

    def start_ssh(self, attempt=0):
        """
        Establishes an ssh connection to the RedPitaya board

        returns True if a successful connection has been established
        """
        try:
            # close pre-existing connection if necessary
            self.end_ssh()
        except (AttributeError, OSError, RuntimeError):
            pass
        if self.parameters["hostname"] == "_FAKE_REDPITAYA_":
            # simulation mode - start without connecting
            self.logger.warning("(Re-)starting client in dummy mode...")
            self.startdummyclient()
            return True
        else:  # normal mode - establish ssh connection and
            try:
                # start ssh connection
                self.ssh = SshShell(
                    hostname=self.parameters["hostname"],
                    sshport=self.parameters["sshport"],
                    user=self.parameters["user"],
                    password=self.parameters["password"],
                    delay=self.parameters["delay"],
                    timeout=self.parameters["timeout"],
                )
                # test ssh connection for exceptions
                self.ssh.ask()
            except Exception as e:  # connection problem
                if attempt < 3:
                    # try to connect up to 3 times
                    return self.start_ssh(attempt=attempt + 1)
                else:  # even multiple attempts did not work
                    raise ExpectedPyrplError(
                        "\nCould not connect to the Red Pitaya device with "
                        "the following parameters: \n\n"
                        "\thostname: {}\n"
                        "\tssh port: {}\n"
                        "\tusername: {}\n"
                        "\tpassword: ****\n\n"
                        "Please confirm that the device is reachable by typing "
                        "its hostname/ip address into a web browser and "
                        "checking that a page is displayed. \n\n"
                        "Error message: {}".format(
                            self.parameters["hostname"],
                            self.parameters["sshport"],
                            self.parameters["user"],
                            e,
                        )
                    )
            else:
                # everything went well, connection is established
                # also establish scp connection
                self.ssh.startscp()
                return True

    def switch_led(self, gpiopin=0, state=False):
        self.ssh.ask("echo " + str(gpiopin) + " > /sys/class/gpio/export")
        sleep(self.parameters["delay"])
        self.ssh.ask("echo out > /sys/class/gpio/gpio" + str(gpiopin) + "/direction")
        sleep(self.parameters["delay"])
        if state:
            state = "1"
        else:
            state = "0"
        self.ssh.ask("echo " + state + " > /sys/class/gpio/gpio" + str(gpiopin) + "/value")
        sleep(self.parameters["delay"])

    def put_file(self, source, destination):
        for i in range(3):
            try:
                self.ssh.scp.put(source, destination)
            except (SCPException, SSHException):
                # try again before failing
                self.start_ssh()
                sleep(self.parameters["delay"])
            else:
                break

    def get_os_version(self):
        self.ssh.ask()  # clear buffer
        result = self.ssh.ask("cat /root/.version")
        self.logger.debug(f"cat /root/.version: {result}")

        # Parse version from response
        version = None
        for line in result.strip().split("\r\n"):
            line = line.strip()
            if line and "cat" not in line and "@" not in line:
                version = line
                break
        if version is None:
            self.logger.warning(f"Could not parse OS version from response: {result}")
            version = "unknown"
        self.logger.debug("OS version: %s", version)
        self.os_version = version

    def update_fpga(self, filename=None, dtbo_filename=None):
        should_reload = self._should_reload_fpga()
        if not should_reload:
            self.logger.error(
                "FPGA update not completed - reloadfpga is False or auto-detected as not needed"
            )
            return

        self._update_fpga(filename, dtbo_filename)

    def _update_fpga(self, filename=None, dtbo_filename=None):
        source = None
        # Determine the base directory for finding files
        base_dir = os.path.abspath(os.path.dirname(__file__))
        self.logger.debug("Base directory: %s", base_dir)

        # Get the source file, with priority order:
        # 1. Function parameter
        # 2. Config parameter
        # 3. Default file (fpga/red_pitaya.bin in the package)
        if filename is not None:
            source = filename
        elif "filename" in self.parameters and self.parameters["filename"]:
            source = self.parameters["filename"]
        else:
            # Use default from package
            source = "fpga/red_pitaya.bin"

        # If source is relative, make it absolute relative to base_dir
        if not os.path.isabs(source):
            source = os.path.join(base_dir, source)

        # Check if file exists
        self.logger.debug("Checking for FPGA binfile at: %s", source)
        if not os.path.isfile(source):
            # List what files are available in the expected directory for debugging
            expected_dir = os.path.dirname(source)
            if os.path.isdir(expected_dir):
                self.logger.error("FPGA binfile not found at: %s", source)
                self.logger.error("Files in %s: %s", expected_dir, os.listdir(expected_dir))
            else:
                self.logger.error("FPGA binfile not found at: %s", source)
                self.logger.error("Directory does not exist: %s", expected_dir)

            raise OSError(
                "FPGA binfile not found",
                "The fpga binfile was not found at: " + source + "\n"
                "Please ensure the file exists or specify a different file with the filename "
                "parameter.",
            )

        self.logger.info("Found FPGA binfile at: %s", source)

        # Get the dtbo source file with same priority order
        dtbo_source = None
        if dtbo_filename is not None:
            dtbo_source = dtbo_filename
        elif "dtbo_filename" in self.parameters and self.parameters["dtbo_filename"]:
            dtbo_source = self.parameters["dtbo_filename"]
        else:
            # Use default dtbo from package (optional)
            dtbo_source = "fpga/red_pitaya.dtbo"

        # If dtbo_source is relative, make it absolute relative to base_dir
        if dtbo_source is not None and not os.path.isabs(dtbo_source):
            dtbo_source = os.path.join(base_dir, dtbo_source)

        # Check if dtbo file exists (it's optional, so just warn if missing)
        if dtbo_source is not None:
            if os.path.isfile(dtbo_source):
                self.logger.info("Found DTBO file at: %s", dtbo_source)
            else:
                self.logger.warning(
                    "DTBO file not found at: %s (continuing without it)", dtbo_source
                )
                dtbo_source = None

        # Prepare the system
        self.end()
        sleep(self.parameters["delay"])
        self.ssh.ask("rw")
        sleep(self.parameters["delay"])
        self.ssh.ask("mkdir -p " + self.parameters["serverdirname"])
        sleep(self.parameters["delay"])

        # send binfile after all checks
        bin_file_path = os.path.join(
            self.parameters["serverdirname"], self.parameters["serverbinfilename"]
        )
        self.put_file(source, bin_file_path)

        update_cmd = f"/opt/redpitaya/sbin/overlay.sh pyrpl {bin_file_path}"

        # add dtbo file to command if it exists
        if dtbo_source is not None:
            dtbo_file_path = os.path.join(
                self.parameters["serverdirname"], self.parameters["serverdtbofilename"]
            )
            self.put_file(dtbo_source, dtbo_file_path)
            update_cmd = f"{update_cmd} {dtbo_file_path}"

        # kill all other servers to prevent reading while fpga is flashed
        self.end()
        self.ssh.ask("killall nginx")
        self.ssh.ask("systemctl stop redpitaya_nginx")  # for 0.94 and higher
        sleep(3)  # sleep after stopping service

        if self.os_version.find("2.") != -1:
            self.ssh.ask(update_cmd)
            sleep(1)
            self.ssh.ask()
            self.ssh.ask("cat /tmp/update_fpga.txt")  # check if fpga is loaded
        else:
            # Old OS version - use xdevcfg directly
            self.logger.info("Loading FPGA via xdevcfg (old OS version)")
            self.ssh.ask(
                "cat "
                + os.path.join(
                    self.parameters["serverdirname"],
                    self.parameters["serverbinfilename"],
                )
                + " > //dev//xdevcfg"
            )

        sleep(3.0)  # wait a bit for the fpga to be programmed
        self.logger.debug("About to restart the redpitaya service")

        # Clean up temporary files in serverdirname
        self.ssh.ask(
            "rm -f "
            + os.path.join(self.parameters["serverdirname"], self.parameters["serverdtbofilename"])
        )
        self.ssh.ask(
            "rm -f "
            + os.path.join(self.parameters["serverdirname"], self.parameters["serverbinfilename"])
        )

        self.ssh.ask("nginx -p //opt//www//")
        self.ssh.ask("systemctl start redpitaya_nginx")  # for 0.94 and higher
        sleep(self.parameters["delay"])
        self.ssh.ask("ro")

    def serverbinfileexists(self):
        self.ssh.ask()
        result = self.ssh.ask(
            "ls {}".format(
                os.path.join(
                    self.parameters["serverdirname"],
                    self.parameters["serverbinfilename"],
                )
            )
        )
        self.logger.debug(f"ls serverbinfilename result: {result}")

        return result.find("No such file or directory") < 0

    def fpgarecentlyflashed(self):
        if not self.serverbinfileexists():
            return False

        self.ssh.ask()
        result = self.ssh.ask(
            'echo $(($(date +%s) - $(date +%s -r "'
            + os.path.join(self.parameters["serverdirname"], self.parameters["serverbinfilename"])
            + '")))'
        )
        age = None
        for line in result.split("\r"):
            try:
                age = int(line.strip())
            except (TypeError, ValueError):
                pass
            else:
                break
        if not age:
            self.logger.debug("Could not retrieve bitfile age from: {}".format(result.split("\r")))
            return False
        elif age > 10:
            self.logger.debug("Found expired bitfile. Age: %s", age)
            return False
        else:
            self.logger.debug("Found recent bitfile. Age: %s", age)
            return True

    def installserver(self):
        self.endserver()
        sleep(self.parameters["delay"])
        self.ssh.ask("rw")
        sleep(self.parameters["delay"])
        self.ssh.ask("mkdir " + self.parameters["serverdirname"])
        sleep(self.parameters["delay"])
        self.ssh.ask("cd " + self.parameters["serverdirname"])
        # try both versions
        for serverfile in ["monitor_server", "monitor_server_0.95"]:
            sleep(self.parameters["delay"])
            try:
                self.ssh.scp.put(
                    os.path.join(
                        os.path.abspath(os.path.dirname(__file__)),
                        "monitor_server",
                        serverfile,
                    ),
                    self.parameters["serverdirname"] + self.parameters["monitor_server_name"],
                )
            except (SCPException, SSHException):
                self.logger.exception("Upload error. Try again after rebooting your RedPitaya..")
            sleep(self.parameters["delay"])
            self.ssh.ask("chmod 755 ./" + self.parameters["monitor_server_name"])
            sleep(self.parameters["delay"])
            self.ssh.ask("ro")
            result = self.ssh.ask(
                "./" + self.parameters["monitor_server_name"] + " " + str(self.parameters["port"])
            )
            sleep(self.parameters["delay"])
            result += self.ssh.ask()
            if "sh" not in result:
                self.logger.debug("Server application started on port %d", self.parameters["port"])
                return self.parameters["port"]
            else:  # means we tried the wrong binary version. make sure server is not running and
                # try again with next file
                self.endserver()

        # try once more on a different port
        if self.parameters["port"] == self.parameters["defaultport"]:
            self.parameters["port"] = random.randint(self.parameters["defaultport"], 50000)
            self.logger.warning(
                "Problems to start the server application. "
                "Trying again with a different port number %d",
                self.parameters["port"],
            )
            return self.installserver()

        self.logger.error(
            "Server application could not be started. Try to recompile monitor_server on your "
            "RedPitaya (see manual). "
        )
        return None

    def startserver(self):
        self.endserver()
        sleep(self.parameters["delay"])
        if self.fpgarecentlyflashed():
            self.logger.info("FPGA is being flashed. Please wait for 2 seconds.")
            sleep(3.0)  # extra second wait time after flashing to avoid bug with the exe
        result = self.ssh.ask(
            self.parameters["serverdirname"]
            + "/"
            + self.parameters["monitor_server_name"]
            + " "
            + str(self.parameters["port"])
        )
        if "sh" not in result:  # sh in result means we tried the wrong binary version
            self.logger.debug("Server application started on port %d", self.parameters["port"])
            self._serverrunning = True
            return self.parameters["port"]
        # something went wrong
        return self.installserver()

    def endserver(self):
        try:
            self.ssh.ask("\x03")  # exit running server application
        except (AttributeError, OSError, RuntimeError):
            self.logger.exception("Server not responding...")
        if "pitaya" in self.ssh.ask():
            self.logger.debug(">")  # formerly 'console ready'
        sleep(self.parameters["delay"])
        # make sure no other monitor_server blocks the port
        self.ssh.ask("killall " + self.parameters["monitor_server_name"])
        self._serverrunning = False

    def endclient(self):
        del self.client
        self.client = None

    def start(self):
        if self.parameters["leds_off"]:
            if self.os_version.find("2.") != -1:  # for os < 0.94
                self.ssh.ask("\x03")
                self.ssh.ask("/opt/redpitaya/bin/led_control -y=Off -e=Off -r=Off")
            else:  # for os > 0.94
                self.switch_led(gpiopin=0, state=False)
                self.switch_led(gpiopin=7, state=False)
        self.startserver()
        sleep(self.parameters["delay"])
        self.startclient()

    def end(self):
        self.endserver()
        self.endclient()

    def end_ssh(self):
        self.ssh.channel.close()

    def end_all(self):
        self.end()
        self.end_ssh()

    def restart(self):
        self.end()
        self.start()

    def restartserver(self, port=None):
        """restart the server. usually executed when client encounters an error"""
        if port is not None:
            if port < 0:  # code to try a random port
                self.parameters["port"] = random.randint(2223, 50000)
            else:
                self.parameters["port"] = port
        return self.startserver()

    def license(self):
        self.logger.info("""\r\n    pyrpl  Copyright (C) 2014-2017 Leonhard Neuhaus
    This program comes with ABSOLUTELY NO WARRANTY; for details read the file
    "LICENSE" in the source directory. This is free software, and you are
    welcome to redistribute it under certain conditions; read the file
    "LICENSE" in the source directory for details.\r\n""")

    def startclient(self):
        self.client = redpitaya_client.MonitorClient(
            self.parameters["hostname"],
            self.parameters["port"],
            restartserver=self.restartserver,
        )
        self.makemodules()
        self.logger.debug("Client started successfully. ")

    def startdummyclient(self):
        self.client = redpitaya_client.DummyClient()
        self.makemodules()

    def makemodule(self, name, cls):
        module = cls(self, name)
        setattr(self, name, module)
        self.modules[name] = module

    def makemodules(self):
        """
        Automatically generates modules from the list RedPitaya.cls_modules
        """
        names = get_unique_name_list_from_class_list(self.cls_modules)
        for cls, name in zip(self.cls_modules, names):
            self.makemodule(name, cls)

    def make_a_slave(self, port=None, monitor_server_name=None, gui=False):
        if port is None:
            port = self.parameters["port"] + len(self._slaves) * 10 + 1
        if monitor_server_name is None:
            monitor_server_name = self.parameters["monitor_server_name"] + str(port)
        slaveparameters = dict(self.parameters)
        slaveparameters.update(
            dict(
                port=port,
                autostart=True,
                reloadfpga=False,
                reloadserver=False,
                monitor_server_name=monitor_server_name,
                silence_env=True,
            )
        )
        r = RedPitaya(**slaveparameters)  # gui=gui)
        r._master = self
        self._slaves.append(r)
        return r
