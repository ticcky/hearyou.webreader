import socket
import threading

class Commander(threading.Thread):
    def __init__(self, ip, port):
        super(Commander, self).__init__()
        self.ip = ip
        self.port = port

        self.sem = threading.Semaphore(0)
        self.lock = threading.RLock()
        self.data = []

    def pop(self):
        self.sem.acquire()
        with self.lock:
            res = self.data[0]
            self.data = self.data[1:]
        return res

    def push(self, item):
        with self.lock:
            self.data.append(item)
            self.sem.release()

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.ip, self.port,))

        while True:
            print 'cmd loop'
            data, addr = sock.recvfrom(1000)
            print data, addr
            data = data.strip()
            for item in data.split('\n'):
                if len(item) > 0:
                    self.push(item)
