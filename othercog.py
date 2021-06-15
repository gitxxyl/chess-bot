# external classes
import json

import discord
from discord.ext import commands

# custom classes
import config


class Other(commands.Cog):
    """Miscellaneous commands for chess bot"""

    # bot init not needed right here
    # def __init__(self, bot):
    #     self.bot = bot

    @commands.command()
    async def stats(self, ctx, user: discord.User = None) -> None:
        """Bot command to send embed of player stats."""
        print()
        player = config.playerlist[
            str(user.id) if user else str(ctx.author.id)]  # get player; param if specified, defaults to author
        await ctx.send(embed=player.getstats())  # call Player.getstats() on player; sends returned embed

    @stats.error
    async def stats_error(self, ctx, error) -> None:  # catch errors thrown in self.stats()
        """Handle UserNotFound error"""
        if isinstance(error, commands.UserNotFound):  # invalid input: user not found
            await ctx.send("Invalid user!")
        else:
            print(config.playerlist)
            print(error)  # prevent errors from going unchecked

    @classmethod
    def save(cls, playerlist: list) -> None:
        """Save current playerlist as a json to stats.json - called at every game end."""
        dictt = config.playerlist  # global playerlist
        for i in playerlist:
            dictt[str(i.id)] = i  # updates global playerlist
            dictt[str(i.id)].winloss = round(i.wins / i.losses if i.losses > 0 else i.wins, 3)  # ensure no div/0 error

        cls.jsonupdate(dictt)  # update stats.json

    @commands.command(name="save")
    async def botsave(self, ctx) -> None:
        """Bot command to save playerlist as a json to stats.json immediately."""
        dictt = config.playerlist  # global playerlist
        self.jsonupdate(dictt)  # sync method
        await ctx.send("Saved!")

    @classmethod
    def jsonupdate(cls, dictt: dict) -> None:
        """Updates the stats.json file through some epic hardcoding"""
        jsondict = {}
        for d in dictt:
            i = dictt.get(d)
            print(type(i))
            print(jsondict)
            jsondict[str(i.id)] = {}
            jsondict[str(i.id)]["name"] = i.name
            jsondict[str(i.id)]["wins"] = i.wins
            jsondict[str(i.id)]["losses"] = i.losses
            jsondict[str(i.id)]["draws"] = i.draws
            jsondict[str(i.id)]["games"] = i.games
            jsondict[str(i.id)]["forfeits"] = i.forfeits
            jsondict[str(i.id)]["stockfish"] = i.stockfish

        with open("stats.json", "w") as f:
            json.dump(jsondict, f)
