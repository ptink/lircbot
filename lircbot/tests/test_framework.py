import unittest
import socket

from lircbot.lircbot import ircBot

MOCK_SERVER = "0.0.0.0"
MOCK_PORT = 50227


class TestFrameworkFunctions(unittest.TestCase):

    def set_up_socket(self):
        # Create stream socket and bind it to the mock server/port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Prevent socket.error "[Errno 98]"
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((MOCK_SERVER, MOCK_PORT))
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
            self.assertFalse(self.bot.is_alive, "Could not stop bot")
        self.sock.close()

    def test_connect(self):
        self.set_up_socket()
        # Instantiate new ircBot and try to connect to the socket
        self.bot = ircBot(MOCK_SERVER, MOCK_PORT, "CreateTest", "Testing the creation of a bot.")
        self.bot.connect()
        try:
            self.bot.sock.recv(1024)
        except socket.error:
            self.fail("Not connected")

        self.assertTrue(self.bot.connected, "Failed to connect")

    def test_disconnect(self):
        self.set_up_socket()
        # Instantiate new ircBot and try to connect to the socket
        self.bot = ircBot(MOCK_SERVER, MOCK_PORT, "CreateTest", "Testing the creation of a bot.")
        self.bot.connect()
        self.assertTrue(self.bot.connected, "Failed to connect")
        self.bot.disconnect()
        self.assertFalse(self.bot.connected, "Failed to disconnect")