"""Various class definitions for use in chesscog.py"""
from enum import Enum, Flag
from typing import Union

import discord


class Player(discord.User):
    """The player object extends the default discord.User class to add additional attributes and methods for discord chess."""

    def __init__(self, *, user: discord.User, userdict: dict) -> None:
        """Initialise Player attributes: wins, losses, etc."""
        # makeshift super() because we dont have the data object to call BaseUser.__init__ on
        self.name = user.name
        self.id = user.id
        self.discriminator = user.discriminator
        self.avatar = user.avatar
        self._public_flags = user._public_flags
        self.bot = user.bot
        self.system = user.system
        self._state = user._state

        # chess attributes
        self.chesscolor: Union[Color, None] = None  # True is white (1), False is black (0)
        self.mode: Union[Mode, None] = None  # Mode is an enum representing singleplayer, multiplayer and variant.
        # self.forfeited: bool = False  # Deprecated attribute for forfeit, replaced with Mode.NULL
        self.opponent: Union[Player, None] = None

        # states attributes (epic hardcoding moment)
        self.wins: int = userdict[str(self.id)]["wins"]
        self.losses: int = userdict[str(self.id)]["losses"]
        self.draws: int = userdict[str(self.id)]["draws"]
        self.games: int = userdict[str(self.id)]["games"]
        self.forfeits: int = userdict[str(self.id)]["forfeits"]
        self.stockfish: int = userdict[str(self.id)]["stockfish"]
        self.winloss: float = round(self.wins / self.losses,
                                    3) if self.losses > 0 else self.wins  # ensure no divide by zero error

    def getstats(self) -> discord.Embed:
        """Create embed object for the player stats command"""
        embed = discord.Embed(colour=discord.colour.Colour.blurple())
        embed.set_author(name=f"{self.name}'s stats")
        embed.add_field(name="Wins", value=str(self.wins))
        embed.add_field(name="Losses", value=str(self.losses))
        embed.add_field(name="Draws", value=str(self.draws))
        embed.add_field(name="Forfeits (counted in losses)", value=str(self.forfeits))
        embed.add_field(name="Games played", value=str(self.games))
        embed.add_field(name="Win/loss ratio", value=str(self.winloss))
        embed.add_field(name="Highest level of stockfish beat", value=str(self.stockfish))

        return embed


class Cancelled(Exception):
    """Custom exception to be used when a game is cancelled prematurely."""
    pass


class Mode(Enum):
    """Enum for current game status of a player object"""
    NULL = 0
    SINGLE = 1
    MULTI = 2
    MULTIV = 3


class Status(Enum):
    """Enum for current game status of bot object"""
    NULL = 0
    REGISTRATION = 1
    GAME = 2


class Color(Flag):
    """Enum for chess colours. Like chess.COLOR, but worse."""
    WHITE = True
    BLACK = False
