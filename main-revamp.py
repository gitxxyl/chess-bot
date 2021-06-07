import os

from discord.ext import commands
from dotenv import load_dotenv
from pretty_help import PrettyHelp

from chesscog import Chess
from othercog import Other
from player import *

if __name__ == '__main__':
    # get environment variables
    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")
    PREFIX = os.getenv("PREFIX")

    # create bot object
    intents = discord.Intents.default()
    intents.members = True  # to access members
    bot = commands.Bot(command_prefix=f"{PREFIX}",
                       help_command=PrettyHelp(color=discord.colour.Colour.blurple(), show_index=False,
                                               no_category="Chess commands"),
                       intents=intents,
                       case_insensitive=True)

    bot.add_cog(Chess(bot))
    bot.add_cog(Other(bot))
    bot.run(TOKEN)
