import requests
import logging


class EG_Discord:
    def __init__(self) -> None:
        self.logger = logging.getLogger("EG Discord")
        self.username = "EG Morserino server"
        self.ready = False
        try:
            with open("discord_hook.txt") as f:
                self.url = f.read()
        except:
            self.logger.warning("Discord config file read error!")
        try:
            self.publishGeneralInfo("Server started", force=True)
            self.ready = True
        except:
            self.logger.warning("Unable to connect do discord")

    def publishOperatorInfo(self, callsign: str, info: str):
        if not self.ready:
            return
        data = {
            "username": "%s : %s" % (self.username, callsign),
            "content": info,
        }
        self.sendMessage(data)

    def publishOperatorMessage(self, callsign, message):
        if not self.ready:
            return
        data = {
            "username": "%s : %s" % (self.username, callsign),
            "content": ">> %s" % (message),
        }
        self.sendMessage(data)

    def publishGeneralInfo(self, info: str, force=False):
        if not self.ready and not force:
            return
        data = {
            "username": "%s" % (self.username),
            "content": "%s" % (info),
        }
        self.sendMessage(data)

    def sendMessage(self, content):
        requests.post(self.url, json=content)
