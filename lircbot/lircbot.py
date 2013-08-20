import socket
import threading
import time


class ircOutputBuffer:
    # Delays consecutive messages by at least 1 second.
    # This prevents the bot spamming the IRC server.
    def __init__(self, irc):
        self.waiting = False
        self.irc = irc
        self.queue = []
        self.error = False

    def __pop(self):
        if len(self.queue) == 0:
            self.waiting = False
        else:
            self.sendImmediately(self.queue[0])
            self.queue = self.queue[1:]
            self.__startPopTimer()

    def __startPopTimer(self):
        self.timer = threading.Timer(1, self.__pop)
        self.timer.start()

    def sendBuffered(self, string):
        # Sends the given string after the rest of the messages in the buffer.
        # There is a 1 second gap between each message.
        if self.waiting:
            self.queue.append(string)
        else:
            self.waiting = True
            self.sendImmediately(string)
            self.__startPopTimer()

    def sendImmediately(self, string):
        # Sends the given string without buffering.
        if not self.error:
            try:
                self.irc.send(bytes(string) + b"\r\n")
            except socket.error, msg:
                self.error = True
                print "Output error", msg
                print "Was sending \"" + string + "\""

    def isInError(self):
        return self.error


class ircInputBuffer:
    # Keeps a record of the last line fragment received by the socket which is usually not a complete line.
    # It is prepended onto the next block of data to make a complete line.
    def __init__(self, irc):
        self.buffer = ""
        self.irc = irc
        self.lines = []
        self.error = False

    def __recv(self):
        # Receives new data from the socket and splits it into lines.
        # Last (incomplete) line is kept for buffer purposes.
        try:
            received = self.irc.recv(4096)
            if not received:
                # No connection
                raise socket.error('No data received')
            data = self.buffer + received
            self.lines += data.split(b"\r\n")
            self.buffer = self.lines[len(self.lines) - 1]
            self.lines = self.lines[:len(self.lines) - 1]
        except socket.error, msg:
            print "Input error", msg
            self.error = True

    def getLine(self):
        # Returns the next line of IRC received by the socket.
        # Converts the received string to standard string format before returning.
        if not self.isInError() and len(self.lines) > 0:
            line = self.lines[0]
            self.lines = self.lines[1:]
            return str(line)
        elif not self.isInError():
            self.__recv()
            time.sleep(1)
        return ""

    def isInError(self):
        return self.error


class ircBot(threading.Thread):
    def __init__(self, network, port, name, description):
        threading.Thread.__init__(self)
        self._debug = False
        self._retries = 5
        self._stop = threading.Event()
        self._to_threshold = 3 * 60  # Default 3 minute timeout
        self.binds = []
        self.connected = False
        self.desc = description
        self.identifyLock = False
        self.identifyNickCommands = []
        self.name = name
        self.network = network
        self.port = port

    # PRIVATE FUNCTIONS
    def __identAccept(self, nick):
        """ Executes all the callbacks that have been approved for this nick
        """
        i = 0
        while i < len(self.identifyNickCommands):
            (nickName, accept, acceptParams, reject, rejectParams) = self.identifyNickCommands[i]
            if nick == nickName:
                accept(*acceptParams)
                self.identifyNickCommands.pop(i)
            else:
                i += 1

    def __identReject(self, nick):
        # Calls the given "denied" callback for all functions called by that nick.
        i = 0
        while i < len(self.identifyNickCommands):
            (nickName, accept, acceptParams, reject, rejectParams) = self.identifyNickCommands[i]
            if nick == nickName:
                reject(*rejectParams)
                self.identifyNickCommands.pop(i)
            else:
                i += 1

    def __callBind(self, msgtype, sender, headers, message):
        # Calls the function associated with the given msgtype.
        for (messageType, callback) in self.binds:
            if messageType == msgtype:
                callback(sender, headers, message)

    def __processLine(self, line):
        # If a message comes from another user, it will have an @ symbol
        if "@" in line:
            # Location of the @ symbol in the line (proceeds sender's domain)
            at = line.find("@")
            # Location of the first gap, this immediately follows the sender's domain
            gap = line[at:].find(" ") + at + 1
            lastColon = line[gap + 1:].find(":") + 2 + gap
        else:
            lastColon = line[1:].find(":") + 1

        # Does most of the parsing of the line received from the IRC network.
        # if there is no message to the line. ie. only one colon at the start of line
        if ":" not in line[1:]:
            headers = line[1:].strip().split(" ")
            message = ""
        else:
            # Split everything up to the lastColon (ie. the headers)
            headers = line[1:lastColon - 1].strip().split(" ")
            message = line[lastColon:]

        sender = headers[0]
        if len(headers) < 2:
            self.__debugPrint("Unhelpful number of messages in message: \"" + line + "\"")
        else:
            if "!" in sender:
                cut = headers[0].find('!')
                if cut != -1:
                    sender = sender[:cut]
                msgtype = headers[1]
                if msgtype == "PRIVMSG" and message.startswith("ACTION ") and message.endswith(""):
                    msgtype = "ACTION"
                    message = message[8:-1]
                self.__callBind(msgtype, sender, headers[2:], message)
            else:
                self.__debugPrint("[" + headers[1] + "] " + message)
                if (headers[1] == "307" or headers[1] == "330") and len(headers) >= 4:
                    self.__identAccept(headers[3])
                if headers[1] == "318" and len(headers) >= 4:
                    self.__identReject(headers[3])
                    #identifies the next user in the nick commands list
                    if len(self.identifyNickCommands) == 0:
                        self.identifyLock = False
                    else:
                        self.outBuf.sendBuffered("WHOIS " + self.identifyNickCommands[0][0])
                self.__callBind(headers[1], sender, headers[2:], message)

    def __debugPrint(self, s):
        if self._debug:
            print s

    # INTERNAL FUNCTIONS
    def _connect(self):
        self.__debugPrint("Connecting...")
        # Setup the socket & input/output buffers
        self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.inBuf = ircInputBuffer(self.irc)
        self.outBuf = ircOutputBuffer(self.irc)
        # Try to connect to the socket
        try:
            self.irc.connect((self.network, self.port))
            self.irc.settimeout(self._to_threshold)
            self.connected = True
        except socket.error as e:
            self.connected = False
            raise e

    def _disconnect(self, qMessage):
        self.__debugPrint("Disconnecting...")
        try:
            self.outBuf.sendBuffered("QUIT :" + qMessage)
            self.irc.close()
            self.connected = False
        except socket.error as e:
            self.connected = False
            raise e

    # PUBLIC FUNCTIONS
    def ban(self, banMask, nick, channel, reason):
        self.__debugPrint("Banning " + banMask + "...")
        self.outBuf.sendBuffered("MODE +b " + channel + " " + banMask)
        self.kick(nick, channel, reason)

    def bind(self, msgtype, callback):
        # Check if the msgtype already exists
        for i in xrange(0, len(self.binds)):
            # Remove msgtype if it has already been "binded" to
            if self.binds[i][0] == msgtype:
                self.binds.remove(i)
        self.binds.append((msgtype, callback))

    def debugging(self, state):
        self._debug = state

    def identify(self, nick, approvedFunc, approvedParams, deniedFunc, deniedParams):
        self.__debugPrint("Verifying " + nick + "...")
        self.identifyNickCommands += [(nick, approvedFunc, approvedParams, deniedFunc, deniedParams)]
        if not self.identifyLock:
            self.outBuf.sendBuffered("WHOIS " + nick)
            self.identifyLock = True

    def join_chan(self, channel):
        self.__debugPrint("Joining " + channel + "...")
        self.outBuf.sendBuffered("JOIN " + channel)

    def kick(self, nick, channel, reason):
        self.__debugPrint("Kicking " + nick + "...")
        self.outBuf.sendBuffered("KICK " + channel + " " + nick + " :" + reason)

    def read_line(self):
        # If the bot is stopped/in error state we want to exit the read loop
        while not self.stop_reading():
            line = self.inBuf.getLine()
            if len(line) > 0:
                if line.startswith("PING"):
                    self.outBuf.sendImmediately("PONG " + line.split()[1])
                else:
                    self.__processLine(line)
        if self.outBuf.isInError() or self.inBuf.isInError():
            self.retry_connection()

    def reconnect(self):
        if self.connected:
            self.__debugPrint("Pausing before reconnecting...")
            self._disconnect("Reconnecting")
            time.sleep(5)
        self._connect()
        self.send_auth_details()

    def retries(self, n):
        self._retries = int(n)

    def retry_connection(self):
        # Attempt to connect n times
        for i in range(self._retries):
            try:
                self.reconnect()
                break
            except socket.error, msg:
                print "Socket error", msg
                if i == (self._retries - 1):
                    # Stop the bot
                    print "Reached maximum number of retries."
                    self.stop()
                else:
                    # Wait before attempting to reconnect
                    time.sleep(2)

    def run(self):
        self.__debugPrint("Bot is now running.")
        while not self.stopped():
            if not self.connected:
                self.retry_connection()
            else:
                self.read_line()
        self.__debugPrint("Bot stopping.")

    def say(self, recipient, message):
        self.outBuf.sendBuffered("PRIVMSG " + recipient + " :" + message)

    def send(self, string):
        self.outBuf.sendBuffered(string)

    def send_auth_details(self):
        if self.connected:
            self.outBuf.sendBuffered("NICK " + self.name)
            self.outBuf.sendBuffered("USER " + self.name + " " + self.name + " " + self.name + " :" + self.desc)

    def stop(self):
        self._stop.set()
        if self.connected:
            self.irc.shutdown(socket.SHUT_WR)

    def stopped(self):
        return self._stop.isSet()

    def stop_reading(self):
        return any([self.stopped(),
                    self.inBuf.isInError(),
                    self.outBuf.isInError()])

    def timeout_threshold(self, t):
        t = float(t)
        if t > 0:
            self._to_threshold = t
        else:
            raise Exception("Timeout threshold must be non-negative.")

    def unban(self, banMask, channel):
        self.__debugPrint("Unbanning " + banMask + "...")
        self.outBuf.sendBuffered("MODE -b " + channel + " " + banMask)
