from scikits.audiolab import Format, Sndfile
from tempfile import mkstemp
from tempfile import NamedTemporaryFile
import socket


from util import strip_accents, leven
import voice
import google_asr


class VoiceCommander(object):
    cmd_dict = {
        ('dalsi', 'dal', ): 'next_news',
        ('predchozi', 'predtim', ): 'prev_news',
        ('stuj', 'stop', 'zastav', ): 'stop',
        ('cti', 'pokracuj', 'coze', 'jednou',): 'read',
        ('vice',) : 'more',
    }

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_cmd(self, cmd):
        print "sending", cmd
        self.sock.sendto(cmd, (self.ip, self.port,))

    def run(self):
        while True:
            wavfile = NamedTemporaryFile()
            voice.record_to_file(wavfile.name)
            print 'recorded', wavfile.name
            asr_res = google_asr.decode_wavefile(wavfile.name)
            print 'asr out', asr_res
            if len(asr_res) > 0:
                best = asr_res[0]
                text = strip_accents(best['utterance'])

                print 'text', text

                res = []
                done = False
                for patterns, cmd in self.cmd_dict.items():
                    for pattern in patterns:
                        ld = leven(pattern, text)
                        if pattern in text or ld < 2:
                            self.send_cmd(cmd)
                            done = True
                            break
                    if done:
                        break
            else:
                self.send_cmd("noentiendo")


def main():
    vc = VoiceCommander("localhost", 12345)
    vc.run()




if __name__ == '__main__':
    main()
