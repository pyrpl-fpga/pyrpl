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

import contextlib
import logging
from time import sleep, time

import paramiko
from scp import SCPClient


class SshShell:
    """This is a wrapper around paramiko.SSHClient and scp.SCPClient
    It provides an ssh connection with the ability to transfer files over it"""

    def __init__(
        self,
        hostname="localhost",
        user="root",
        password="root",
        delay=0.05,
        timeout=3,
        sshport=22,
        shell=True,
    ):
        self._logger = logging.getLogger(name=__name__)
        self.delay = delay
        self.apprunning = False
        self.hostname = hostname
        self.sshport = sshport
        self.user = user
        self.password = password
        self.timeout = timeout
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            hostname,
            username=self.user,
            password=self.password,
            port=self.sshport,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        if shell:
            self.channel = self.ssh.invoke_shell()
        self.startscp()

    def startscp(self):
        self.scp = SCPClient(self.ssh.get_transport())

    def write(self, text):
        if self.channel.send_ready() and text != "":
            return self.channel.send(text)
        else:
            return -1

    def read_nbytes(self, nbytes):
        if self.channel.recv_ready():
            return self.channel.recv(nbytes)
        else:
            return b""

    def read(self, timeout=None):
        """
        Read available data from the channel with optional timeout.

        Args:
            timeout: Maximum time to wait for data (seconds). If None, uses self.delay
        """
        if timeout is None:
            timeout = self.delay * 10  # Default: wait longer than a single delay

        sumstring = ""
        start_time = time()

        # Keep reading until no more data or timeout
        while (time() - start_time) < timeout:
            if self.channel.recv_ready():
                string = self.read_nbytes(1024).decode("utf-8")
                sumstring += string
                start_time = time()  # Reset timeout on new data
            else:
                sleep(0.01)  # Small sleep to avoid busy-waiting

            # If we got some data and haven't received more for a bit, assume we're done
            if sumstring and not self.channel.recv_ready():
                sleep(self.delay)
                if not self.channel.recv_ready():
                    break

        self._logger.debug(sumstring)
        return sumstring

    def askraw(self, question=""):
        # Clear any pending output first
        if question:
            self.read_nbytes(65536)  # Clear buffer
            sleep(self.delay)

        self.write(question)
        sleep(self.delay)
        return self.read()

    def ask(self, question=""):
        return self.askraw(question + "\n")

    def __del__(self):
        self.endapp()
        with contextlib.suppress(AttributeError):  # already broken
            self.channel.close()
        self.ssh.close()

    def endapp(self):
        pass

    def reboot(self):
        self.endapp()
        self.ask("shutdown -r now")
        self.__del__()

    def shutdown(self):
        self.endapp()
        self.ask("shutdown now")
        self.__del__()

    def get_mac_addresses(self):
        """
        returns all MAC addresses of the SSH device.
        """
        self.ask()  # empty the shell before asking something
        macs = list()
        nextgood = False
        for token in self.ask("ifconfig | grep HWaddr").split():
            if nextgood and len(token.split(":")) == 6:
                macs.append(token)
            nextgood = token == "HWaddr"
        if macs == []:  # problem on more recent redpitaya os
            nextgood = False
            for token in self.ask("ip address").split():
                if nextgood and len(token.split(":")) == 6:
                    macs.append(token)
                nextgood = token == "link/ether"
        return macs
