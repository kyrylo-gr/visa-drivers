import logging
import socket  # pylint: disable=import-error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SerialFromLAN(object):
    """
    This object can be either a Wiznet converting Ethernet socket commands
    into serial commands or a simple Serail connection. In any case,
    the connection is "normally-closed" between blocking function calls.
    """
    TCP_PORT = 5000
    BUFFER_SIZE = 1024

    def __init__(self,
                 ip: str,
                 linebreak: str = '\n',
                 timeout: float = .1):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.linebreak = linebreak
        self.socket.settimeout(timeout)
        try:
            self.socket.connect((ip, self.TCP_PORT))
        except socket.error:
            logger.error("could not connect to ip: %s", ip)
        else:
            self.socket.setblocking(True)

        # self.socket.settimeout(1)

    def write(self, val):
        self.socket.send(val.encode('utf-8'))

    def read(self):
        """Read data from the socket until socket.error is reached"""
        answer = ''
        while(True):
            try:
                answer += self.socket.recv(self.BUFFER_SIZE).decode('utf-8')
            except socket.error:
                return answer

    def readline(self):
        """Read a line from the socket. Reads until socket.error or line-break character."""
        answer = ''
        char = ''
        while (char != self.linebreak.encode('utf-8')):
            try:
                char = self.socket.recv(1)
                answer += char.decode("utf-8")
                if len(char.decode("utf-8")) == 0:
                    return answer
            except socket.error:
                return answer
        return answer

    def ask(self, val, timeout=-1):
        """Send a query and read a line of response"""
        if timeout > 0:
            raise NotImplementedError("timeout is not implemented")
        self.write(val)
        return self.readline()
