import unittest
import socket
import time

from lircbot.lircbot import ircBot

FAKE_SERVER = "0.0.0.0"
FAKE_PORT = 50227


class TestFrameworkFunctions(unittest.TestCase):

    def set_up_socket(self):
        # Create stream socket and bind it to the mock server/port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Prevent socket.error "[Errno 98]"
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((FAKE_SERVER, FAKE_PORT))
        # Listen for connections with a timeout of 100 seconds
        self.sock.listen(0)
        self.sock.settimeout(100.0)

    def setUp(self):
        self.sock = socket.socket()
        self.bot = None

    def tearDown(self):
        if self.bot.is_alive():
            self.bot.stop()
            self.bot.join(5)
            self.assertFalse(self.bot.is_alive(), "Could not stop bot")
        self.sock.close()

    def test_connect(self):
        self.set_up_socket()
        # Instantiate new ircBot and try to connect to the socket
        self.bot = ircBot(FAKE_SERVER, FAKE_PORT, "ConnectTest", "Testing the bot connect function")
        self.bot.connect()
        time.sleep(3)  # Give bot time to send messages
        self.assertTrue(self.bot.connected, "Failed to connect")

    def test_disconnect(self):
        self.set_up_socket()
        # Instantiate new ircBot and try to connect to the socket
        self.bot = ircBot(FAKE_SERVER, FAKE_PORT, "DisconnectTest", "Testing the bot disconnect function")
        self.bot.connect()
        time.sleep(3)  # Give bot time to send messages
        # Try to disconnect from the socket
        self.bot.disconnect("disconnecting...")
        self.assertFalse(self.bot.connected, "Failed to disconnect")
