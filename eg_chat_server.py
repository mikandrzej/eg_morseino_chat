import socket
import time
import requests

SERVER_IP = "0.0.0.0"
UDP_PORT = 7373
MAX_CLIENTS = 10
KEEPALIVE = 0.2
DEBUG = 1

serversock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serversock.bind((SERVER_IP, UDP_PORT))
serversock.settimeout(KEEPALIVE)

receivers = {}


def debug(str):
    if DEBUG:
        print(str)


class DiscordHook:
    def __init__(self) -> None:
        self.url = "https://discord.com/api/webhooks/1158490293641941052/X2fIvUQ0r4ex9IBftBIYzGBSl7T9ZWR9qhdvaYWv29eQO0ghJrNYSQWdIbsWl2RkXvJp"
        self.username = "Morserino server"
        pass

    def publishOperatorInfo(self, callsign: str, info: str):
        data = {
            "username": "%s : %s" % (self.username, callsign),
            "content": info,
        }
        self.sendMessage(data)

    def publishOperatorMessage(self, callsign, message):
        data = {
            "username": "%s : %s" % (self.username, callsign),
            "content": ">> %s" % (message),
        }
        self.sendMessage(data)

    def sendMessage(self, content):
        requests.post(self.url, json=content)


discordHook = DiscordHook()


class Mopper:
    morse = {
        "0": "-----",
        "1": ".----",
        "2": "..---",
        "3": "...--",
        "4": "....-",
        "5": ".....",
        "6": "-....",
        "7": "--...",
        "8": "---..",
        "9": "----.",
        "A": ".-",
        "B": "-...",
        "C": "-.-.",
        "D": "-..",
        "E": ".",
        "F": "..-.",
        "G": "--.",
        "H": "....",
        "I": "..",
        "J": ".---",
        "K": "-.-",
        "L": ".-..",
        "M": "--",
        "N": "-.",
        "O": "---",
        "P": ".--.",
        "Q": "--.-",
        "R": ".-.",
        "S": "...",
        "T": "-",
        "U": "..-",
        "V": "...-",
        "W": ".--",
        "X": "-..-",
        "Y": "-.--",
        "Z": "--..",
        "=": "-...-",
        "/": "-..-.",
        "+": ".-.-.",
        "-": "-....-",
        ".": ".-.-.-",
        ",": "--..--",
        "?": "..--..",
        ":": "---...",
        "!": "-.-.--",
        "'": ".----.",
        "<ERR>": "......",
        "<KN>": "-.--.",
        "<BK>": "-...-.-",
        "<EXIT>": "..--..--",
        " ": "^",
    }
    morse_rev = {v: k for k, v in morse.items()}

    def __init__(self) -> None:
        self.mopp = b""
        self.bitmopp = ""
        self.cwmopp = ""
        self.dida = ""
        self.text = ""
        self.protocol_version = 1
        self.serial = 0
        self.speed = 20
        pass

    def from_mopp(self, mopp: bytearray):
        self.mopp = mopp
        self.bitmopp = self.mopp_to_bitmopp(mopp)
        self.protocol_version = self.bitarray_to_int(self.bitmopp[0:2])
        self.serial = self.bitarray_to_int(self.bitmopp[2:8])
        self.speed = self.bitarray_to_int(self.bitmopp[8:14])
        self.cwbitmopp = self.bitmopp[14:]
        self.dida = self.cwbitmopp_to_dida(self.cwbitmopp)
        self.text = self.dida_to_text(self.dida).strip()

    def from_text(self, text: str, speed: int = 25, proto_version: int = 1):
        self.text = text.upper().strip()
        self.dida = self.text_to_dida(self.text).strip()
        self.cwbitmopp = self.dida_to_cwbitmopp(self.dida)
        self.speed = speed
        self.serial = (self.serial + 1) % 64
        self.protocol_version = proto_version
        self.bitmopp = (
            self.int_to_bitarray(self.protocol_version, 2)
            + self.int_to_bitarray(self.serial, 6)
            + self.int_to_bitarray(self.speed, 6)
            + self.cwbitmopp
        )
        self.mopp = self.bitmopp_to_mopp(self.bitmopp)

    def mopp_to_bitmopp(self, mopp: bytearray):
        result = ""
        for x in mopp:
            for bit in range(7, -1, -1):
                val = x & (1 << bit)
                if val > 0:
                    result += "1"
                else:
                    result += "0"
        return result

    def cwbitmopp_to_dida(self, cwbitmopp: str):
        result = ""
        for x in range(0, len(cwbitmopp), 2):
            val = cwbitmopp[x : x + 2]
            if val == "01":
                result += "."
            elif val == "10":
                result += "-"
            elif val == "00":
                result += " "
            elif val == "11":
                result += " ^ "
        return result

    def dida_to_text(self, dida: str):
        result = ""
        dida_spl = dida.strip().split(" ")
        for x in dida_spl:
            if x in self.morse_rev:
                result += self.morse_rev[x]
            else:
                result += "*"
        return result

    def text_to_dida(self, text: str):
        dida = ""
        idx = 0
        while idx < len(text):
            if idx > 0:
                dida += " "
            val = text[idx]
            if val == "<":
                if idx + 4 > len(text):
                    break
                val = text[idx : idx + 4]
            if val in self.morse:
                dida += self.morse[val]
            idx += len(val)
        return dida

    def dida_to_cwbitmopp(self, dida: str):
        cwbitmopp = ""
        dida_spl = dida.split(" ")
        for ind, x in enumerate(dida_spl):
            if ind > 0 and x != "^":
                cwbitmopp += "00"
            for c in x:
                if c == ".":
                    cwbitmopp += "01"
                elif c == "-":
                    cwbitmopp += "10"
                elif c == "^":
                    cwbitmopp += "11"
        return cwbitmopp

    def bitmopp_to_mopp(self, bitmopp: str):
        padding = 8 - len(bitmopp) % 8 if len(bitmopp) % 8 > 0 else 0
        tmp_bitmopp = bitmopp + padding * "0"
        mopp = b""
        while len(tmp_bitmopp) > 0:
            byte = tmp_bitmopp[:8]
            tmp_bitmopp = tmp_bitmopp[8:]
            val = self.bitarray_to_int(byte).to_bytes()
            mopp += val
        return mopp

    def bitarray_to_int(self, bitarray: str):
        value = 0
        for bit in range(len(bitarray)):
            bit_value = bitarray[bit]
            bit_pos = len(bitarray) - bit - 1
            if bit_value == "1":
                value = value | (1 << bit_pos)
        return value

    def int_to_bitarray(self, val: int, bit_len: int):
        bitarray = ""
        for pos in range(bit_len):
            bit_pos = bit_len - pos - 1
            if val & (1 << bit_pos) > 0:
                bitarray += "1"
            else:
                bitarray += "0"
        return bitarray


class Client:
    states = ["NOT_LOGGED_IN", "LOGGED_IN", "CQ", "CALL", "CALL_CONNECTED"]

    def __init__(self, ip, port) -> None:
        self.ip = ip
        self.port = port
        self.callsign = ""
        self.rec_mopper = Mopper()
        self.send_mopper = Mopper()
        self.received_text = ""
        self.state = self.states[0]
        self.partner_client = None
        self.discord_message = ""
        self.discord_publish_timeout = None
        self.last_sent_time = time.time()
        self.text_to_send = []
        self.activity_timeout = time.time() + 600
        self.to_delete = False
        pass

    def __str__(self) -> str:
        return "%s:%s" % (self.ip, str(self.port))

    def process_data(self, data):
        self.rec_mopper.from_mopp(data)
        text = self.rec_mopper.text

        debug("Received data: " + self.rec_mopper.text)

        state_mapper = {
            "NOT_LOGGED_IN": self.state_not_logged_in,
            "LOGGED_IN": self.state_logged_in,
            "CQ": self.state_cq,
            "CALL": self.state_call,
            "CALL_CONNECTED": self.state_call_connected,
        }
        state_mapper[self.state](text)
        self.activity_timeout = time.time() + 600

    def send_text(self, text: str, speed: int = -1):
        if speed < 0:
            if self.rec_mopper.speed > 0:
                speed = self.rec_mopper.speed
            else:
                speed = 25
        to_send = text.split(" ")
        to_send = [(x, speed) for x in to_send]
        self.text_to_send += to_send

    def check_timeouts(self):
        if self.discord_publish_timeout is not None:
            if time.time() > self.discord_publish_timeout:
                discordHook.publishOperatorMessage(self.callsign, self.discord_message)
                self.discord_publish_timeout = None
                self.discord_message = ""
        if len(self.text_to_send) > 0:
            if time.time() - self.last_sent_time > 0.5:
                to_send = self.text_to_send[0]
                self.text_to_send = self.text_to_send[1:]
                self.send_mopper.from_text(to_send[0], to_send[1])
                serversock.sendto(self.send_mopper.mopp, (self.ip, self.port))
        
        if time.time() > self.activity_timeout:
            discordHook.publishOperatorInfo(self.callsign, "Operator logged out - activity timeout (600s)")
            self.to_delete = True


    def append_text_to_send(self, text: str):
        if len(self.text_to_send) > 0:
            self.text_to_send += " "
        self.text_to_send += text

    def append_received_text(self, text: str):
        if len(self.received_text) > 0:
            self.received_text += " "
        self.received_text += text

    def state_not_logged_in(self, text: str):
        self.append_received_text(text)
        if text == "<ERR>":
            self.received_text = ""
        if self.received_text.endswith(" K"):
            spl_text = self.received_text.split(" ")
            if len(spl_text) == 3 and spl_text[0] == "DE":
                self.callsign = spl_text[1]
                self.received_text = ""
                self.state = "LOGGED_IN"
                self.send_text("HI " + self.callsign, 60)
                discordHook.publishOperatorInfo(self.callsign, "Operator is online")
            else:
                self.received_text = ""
                self.send_text("ERR. FORMAT IS :DE /CALLSIGN/ K:", 60)
        pass

    def state_logged_in(self, text: str):
        if text == "?":
            self.send_text(":1 = CQ, 2 = CALL:", 60)
        elif text == "1":
            self.state = "CQ"
            self.send_text("CQ MODE", 60)
            discordHook.publishOperatorInfo(self.callsign, "Operator is in CQ mode")
        elif text == "2":
            self.state = "CALL"
            self.send_text("ENTER CALLSIGN", 60)
        else:
            self.send_text(":? for help:", 60)

    def state_cq(self, text: str):
        if len(self.discord_message) > 0:
            self.discord_message += " "
        self.discord_message += text
        if text == "K" or text == "<KN>" or text == "<EXIT>":
            self.discord_publish_timeout = time.time()
            if text == "<EXIT>":
                self.state = "LOGGED_IN"
                self.state_logged_in("?")
        else:
            self.discord_publish_timeout = time.time() + 8.0

    def state_call(self, text: str):
        if text == "?":
            self.send_text(":0 = EXIT:", 60)
        elif text == "0":
            self.state = "LOGGED_IN"
            self.state_logged_in("?")
        else:
            callsign = text
            for client in receivers:
                if receivers[client].callsign == callsign:
                    self.partner_client = receivers[client]
            if self.partner_client is not None:
                self.send_text(
                    ":CONNECTED TO " + callsign + ":TO EXIT SEND ..--..--:", 60
                )
                self.state = "CALL_CONNECTED"
            else:
                self.send_text(":" + callsign + " NOT LOGGED IN:", 60)

    def state_call_connected(self, text: str):
        if text == "<EXIT>":
            self.state = "LOGGED_IN"
            self.state_logged_in("?")
        elif self.partner_client is not None:
            self.partner_client.send_text(text, self.rec_mopper.speed)


while KeyboardInterrupt:
    try:
        data, addr = serversock.recvfrom(64)
        client = Client(addr[0], addr[1])
        if str(client) not in receivers:
            receivers[str(client)] = client

        receivers[str(client)].process_data(data)

        mopp = Mopper()
        mopp.from_mopp(data)

    except socket.timeout:
        # Send UDP keepalives
        for c in receivers.keys():
            ip, port = c.split(":")
            serversock.sendto(b"", (ip, int(port)))
        pass

    except (KeyboardInterrupt, SystemExit):
        serversock.close()
        break
        pass

    to_delete = []
    for receiver in receivers:
        client = receivers[receiver]
        if client.to_delete:
            to_delete.append(receiver)
        else:
            client.check_timeouts()
    
    for receiver in to_delete:
        receivers.pop(receiver)
