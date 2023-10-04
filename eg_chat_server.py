import socket
import time
import requests
import logging
from eg_discord import EG_Discord
from eg_mopper import EG_Mopper
from eg_data_provider import EG_Data_Provider

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

SERVER_IP = "0.0.0.0"
UDP_PORT = 7373
MAX_CLIENTS = 100
KEEPALIVE = 0.2
TIMEOUT = 0.1

serversock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serversock.bind((SERVER_IP, UDP_PORT))
serversock.settimeout(TIMEOUT)

logger = logging.getLogger("EG Chat server")

discordHook = EG_Discord()

data_provider = EG_Data_Provider("eg_database.db")


class Client:
    states = ["NOT_LOGGED_IN", "LOGGED_IN", "CQ", "CALL", "CALL_CONNECTED"]

    def __init__(self, ip, port, morserino) -> None:
        self.ip = ip
        self.port = port
        self.callsign = ""
        self.rec_mopper = EG_Mopper()
        self.send_mopper = EG_Mopper()
        self.received_text = ""
        self.state = self.states[0]
        self.partner_client = None
        self.discord_message = ""
        self.discord_publish_timeout = None
        self.last_sent_time = time.time()
        self.text_to_send = []
        self.activity_timeout = time.time() + 600
        self.to_delete = False
        self.morserino = morserino
        pass

    def __str__(self) -> str:
        return "%s:%s" % (self.ip, str(self.port))

    def process_data(self, data):
        self.rec_mopper.from_mopp(data)
        text = self.rec_mopper.text

        logger.debug("Received data: " + self.rec_mopper.text)

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
        elif text == "?":
            self.send_text(":Please login with /DE CALLSIGN K/:")
            self.received_text = ""
        elif self.received_text.endswith(" K"):
            spl_text = self.received_text.split(" ")
            if len(spl_text) == 3 and spl_text[0] == "DE":
                self.callsign = spl_text[1]
                self.received_text = ""
                self.send_text("HI " + self.callsign + " ? - help", 60)
                discordHook.publishOperatorInfo(self.callsign, "Operator is online")
                self.state = "LOGGED_IN"
            else:
                self.received_text = ""
                self.send_text(":Format error. Please login with /DE CALLSIGN K/:", 60)
        pass

    def state_logged_in(self, text: str):
        if text == "?":
            self.send_text(":1 = CQ, 2 = QSO:", 60)
        elif text == "1":
            self.state = "CQ"
            self.send_text(":CQ MODE. To exit send <SK>:", 60)
            discordHook.publishOperatorInfo(self.callsign, "Operator is in CQ mode")
        elif text == "2":
            self.state = "CALL"
            self.send_text(":ENTER CALLSIGN:", 60)
        else:
            self.send_text(":? for help:", 60)

    def state_cq(self, text: str):
        if len(self.discord_message) > 0:
            self.discord_message += " "
        if text == "K" or text == "<KN>" or text == "<SK>":
            self.discord_publish_timeout = time.time()
            if text == "<SK>":
                self.state = "LOGGED_IN"
                self.state_logged_in("?")
                discordHook.publishOperatorInfo(self.callsign, "Operator leaves CQ mode")
            else:    
                self.discord_message += text
        else:
            self.discord_message += text
            self.discord_publish_timeout = time.time() + 8.0
        
        self.morserino.send_to_cq_channel(self, text)
        

    def state_call(self, text: str):
        if text == "?":
            self.send_text(":0 = EXIT:", 60)
        elif text == "0":
            self.state = "LOGGED_IN"
            self.state_logged_in("?")
        else:
            partner_callsign = text
            partner_client = self.morserino.get_client_for_callsign(partner_callsign)
            if partner_client is not None:
                self.partner_client = partner_client
                self.send_text(
                    ":CONNECTED TO " + partner_callsign + ":TO EXIT SEND <SK>:", 60
                )
                discordHook.publishOperatorInfo(self.callsign, "Operator is in QSO mode with %s" % partner_callsign)
                self.state = "CALL_CONNECTED"
            else:
                self.send_text(":" + partner_callsign + " NOT LOGGED IN:", 60)

    def state_call_connected(self, text: str):
        if text == "<SK>":
            self.state = "LOGGED_IN"
            self.state_logged_in("?")
            discordHook.publishOperatorInfo(self.callsign, "Operator leaves QSO mode")
        elif self.partner_client is not None:
            if not self.partner_client.to_delete:
                self.partner_client.send_text(text, self.rec_mopper.speed)


class Morserino:
    def __init__(self) -> None:
        self.receivers = {}
    
    def process_data(self, ip, port, data):
        client_str = self.ip_port_to_str(ip, port)
        if client_str not in self.receivers:
            client = Client(ip, port, self)
            self.receivers[client_str] = client
        else:
            client = self.receivers[client_str]
        client.process_data(data)
    
    def cyclic(self):
        to_delete = []
        for receiver in self.receivers:
            client = self.receivers[receiver]
            if client.to_delete:
                to_delete.append(receiver)
            else:
                client.check_timeouts()
        
        for receiver in to_delete:
            self.receivers.pop(receiver)
    
    def ip_port_to_str(self, ip, port):
        return (str(ip) + ":" + str(port))

    def get_client_for_callsign(self, callsign):
        for receiver in self.receivers:
            client = self.receivers[receiver]
            if client.callsign == callsign:
                return client
        return None
    
    def send_to_cq_channel(self, sender, data):
        for receiver in self.receivers:
            client = self.receivers[receiver]
            if client != sender:
                if client.state == "CQ":
                    client.send_text(data)


morserino = Morserino()


while KeyboardInterrupt:
    try:
        data, addr = serversock.recvfrom(64)
        morserino.process_data(addr[0], addr[1], data)

        receivers[str(client)].process_data(data)
    except :
        pass

    morserino.cyclic()
