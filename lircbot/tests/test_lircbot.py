import unittest
import socket
from mock import patch, Mock, MagicMock

from lircbot.lircbot import ircBot

FAKE_SERVER = "0.0.0.0"
FAKE_PORT = 50227
TIMEOUT_THRESHOLD = 3 * 60

@patch('lircbot.lircbot.socket.socket')
class TestBotConnect(unittest.TestCase):

    def setUp(self):
        # Instantiate new ircBot and try to connect to the socket
        self.bot = ircBot(FAKE_SERVER, FAKE_PORT, "ConnectTest", "Testing the bot connect function")

    def tearDown(self):
        if self.bot.is_alive():
            self.bot.stop()
            self.bot.join(10)

    def test_socket_connect_called(self, mock_socket):
        # Run _connect, test socket connect called correctly
        self.bot._connect()
        self.bot.irc.connect.assert_called_once_with((FAKE_SERVER, FAKE_PORT))

    def test_socket_timeout_set(self, mock_socket):
        # Set bot timeout
        self.bot.timeout_threshold(TIMEOUT_THRESHOLD)
        # Run _connect, test socket timeout called correctly
        self.bot._connect()
        self.bot.irc.settimeout.assert_called_once_with(TIMEOUT_THRESHOLD)

    def test_bot_connected_set(self, mock_socket):
        # Run _connect, test that bot's connected variable set correctly
        self.bot._connect()
        self.assertTrue(self.bot.connected)

    def test_socket_error_raised(self, mock_socket):
        # Set mock socket connect method to raise a socket error
        mock_socket().connect = MagicMock(side_effect=socket.error((111, '[Errno 111] Connection refused')))
        # Check socket error raised
        self.assertRaises(socket.error, self.bot._connect)
        self.assertFalse(self.bot.connected)
