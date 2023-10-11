import socket
import time
import logging
from eg_mopper import EG_Mopper
from discord_webhook import DiscordWebhook

logging.basicConfig()
logging.root.setLevel(logging.DEBUG)

SERVER_IP = "0.0.0.0"
UDP_PORT = 7373
MAX_CLIENTS = 100
KEEPALIVE = 0.2
TIMEOUT = 0.1

ACTIVITY_TIMEOUT = 30
KICKOFF_TIMEOUT = 60 * 60 * 6

ROOM_NUMBERS = 3

ECHO_ON = True

serversock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serversock.bind((SERVER_IP, UDP_PORT))
serversock.settimeout(TIMEOUT)

logger = logging.getLogger("EG Chat server")


class Client:
    states = ["NOT_LOGGED_IN", "LOGGED_IN", "AIR"]

    def __init__(self, ip, port, morserino) -> None:
        self.ip = ip
        self.port = port
        self.callsign = ""
        self.rec_mopper = EG_Mopper()
        self.send_mopper = EG_Mopper()
        self.received_text = ""
        self.state = self.states[0]
        self.partner_client = NotImplemented
        self.discord_publish_timeout = None
        self.last_sent_time = time.time()
        self.text_to_send = []
        self.reset_timeouts()
        self.to_delete = False
        self.morserino = morserino
        self.room_no = 0
        pass

    def __str__(self) -> str:
        return "%s:%s" % (self.ip, str(self.port))

    def process_data(self, data):
        self.rec_mopper.from_mopp(data)
        text = self.rec_mopper.text

        logger.debug(
            str(self)
            + ": Received data "
            + str(self.rec_mopper.speed)
            + "WPM: "
            + self.rec_mopper.text
        )

        state_mapper = {
            "NOT_LOGGED_IN": self.state_not_logged_in,
            "LOGGED_IN": self.state_logged_in,
            "AIR": self.state_air,
        }
        state_mapper[self.state](text)
        self.reset_timeouts()

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
        if len(self.text_to_send) > 0:
            if time.time() - self.last_sent_time > 0.5:
                to_send = self.text_to_send[0]
                self.text_to_send = self.text_to_send[1:]
                self.send_mopper.from_text(to_send[0], to_send[1])
                serversock.sendto(self.send_mopper.mopp, (self.ip, self.port))

                logger.debug("Sent [ " + str(to_send) + " ] to: " + str(self))

        if time.time() > self.kickoff_timeout:
            self.morserino.general_room.send_discord_msg(
                self.callsign, "Operator logged out - activity timeout (600s)"
            )
            logger.debug("Operator logged out due to timoeut: " + str(self))
            self.to_delete = True

        if time.time() > self.activity_timeout:
            logger.debug("Operator activity timoeut: " + str(self))
            serversock.sendto(b"", (self.ip, self.port))
            self.activity_timeout += ACTIVITY_TIMEOUT

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
            self.send_text(":Please login with /DE CALLSIGN K/:", 60)
            self.received_text = ""
        elif self.received_text.endswith(" K"):
            spl_text = self.received_text.split(" ")
            if len(spl_text) == 3 and spl_text[0] == "DE":
                self.callsign = spl_text[1]
                self.received_text = ""
                self.morserino.general_room.send_discord_msg(
                    self.callsign, "Operator logged in"
                )
                self.state = "LOGGED_IN"
                self.state_logged_in("?")
            else:
                self.received_text = ""
                self.send_text(":Please login with /DE CALLSIGN K/:", 60)
        pass

    def state_logged_in(self, text: str):
        if text == "?":
            self.send_text(
                ":Enter room number 1-%d. <SK> to logout:" % ROOM_NUMBERS, 60
            )
        elif text == "<SK>":
            self.state_not_logged_in("?")
            self.state = "NOT_LOGGED_IN"
            self.morserino.general_room.send_discord_msg(
                self.callsign, "Operator logged out"
            )

        elif text.isdigit():
            room_no = int(text)
            if room_no < 1 or room_no > ROOM_NUMBERS:
                self.send_text(":Invalid room number:", 60)
            else:
                self.join_room(room_no)
        else:
            self.send_text(":? for help:", 60)

    def join_room(self, room_no: int):
        self.room_no = room_no
        self.room = self.morserino.get_room(room_no)
        self.room.join(self)
        self.state = "AIR"
        self.morserino.general_room.send_discord_msg(
            self.callsign, "Operator joined room %d" % self.room_no
        )
        self.send_text(":Joined room %d:" % room_no, 60)

    def exit_room(self):
        self.room.exit(self)
        self.room = None
        self.state = "LOGGED_IN"
        self.state_logged_in("?")
        self.morserino.general_room.send_discord_msg(
            self.callsign, "Operator leaves room %d" % self.room_no
        )

    def state_air(self, text: str):
        self.room.send_msg(self, text, self.rec_mopper.speed)
        if text == "<SK>":
            self.exit_room()

    def reset_timeouts(self):
        self.activity_timeout = time.time() + ACTIVITY_TIMEOUT
        self.kickoff_timeout = time.time() + KICKOFF_TIMEOUT


class Room:
    def __init__(self, hook_address) -> None:
        self.hook_address = hook_address
        self.subscribers = []
        self.last_sent_client = None

    def join(self, client):
        if client not in self.subscribers:
            self.subscribers.append(client)

    def exit(self, client):
        if client in self.subscribers:
            self.subscribers.remove(client)

    def send_discord_msg(self, username, message):
        if self.hook_address is not None:
            DiscordWebhook(
                self.hook_address, username=username, content=message
            ).execute()

    def send_msg(self, client, message: str, speed):
        for subscriber in self.subscribers:
            if subscriber != client or ECHO_ON:
                subscriber.send_text(message)
        if client != self.last_sent_client:
            if self.hook_address is not None:
                self.last_message = DiscordWebhook(
                    self.hook_address, username=client.callsign, content=message
                )
                self.last_message.execute()
                self.last_sent_client = client
        else:
            if message == "K":
                message = "K\n"
            else:
                message = message.replace("<KN>", "<KN>\n").replace("=", "=\n")

            self.last_message.content += " " + message
            self.last_message.edit()


class Morserino:
    def __init__(self) -> None:
        self.receivers = {}
        self.general_room = None
        self.rooms = []
        self.init_rooms()

    def init_rooms(self):
        urls = [None] * (ROOM_NUMBERS + 1)
        try:
            with open("discord_hook.txt") as f:
                urls = [x.strip() for x in f.readlines()]
        except:
            logger.warning('Error occured during read "discord_hook.txt" file.')

        if len(urls) == ROOM_NUMBERS + 1:
            self.general_room = Room(urls[0])
            self.general_room.send_discord_msg("Morserino Server", "Server started")
            for url in urls[1:]:
                room = Room(url)
                self.rooms.append(room)
        else:
            logger.error("Invalid hooks number")

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
        return str(ip) + ":" + str(port)

    def get_client_for_callsign(self, callsign):
        for receiver in self.receivers:
            client = self.receivers[receiver]
            if client.callsign == callsign:
                return client
        return None

    def get_room(self, number: int):
        if number <= len(self.rooms):
            return self.rooms[number - 1]
        return None


morserino = Morserino()


while KeyboardInterrupt:
    try:
        data, addr = serversock.recvfrom(64)
        morserino.process_data(addr[0], addr[1], data)

        receivers[str(client)].process_data(data)
    except:
        pass

    morserino.cyclic()
