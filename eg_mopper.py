class EG_Mopper:
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
        "Ä": ".-.-",
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
        "Ü": "..--",
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
        "<AS>": ".-...",
        "<ERR>": "......",
        "<KN>": "-.--.",
        "<BK>": "-...-.-",
        "<SK>": "...-.-",
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
