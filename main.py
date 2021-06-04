import asyncio
import json
import os
import random
import re
import chess
import chess.svg
import chess.engine
import discord
from RepeatedTimer import RepeatedTimer
from cairosvg import svg2png
from discord.ext import commands
from dotenv import load_dotenv
from pretty_help import PrettyHelp

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX")
intents = discord.Intents.default()
intents.members = True
timedout = False
illegal = False
forfeited = False
onetwovar = "2"
bot = commands.Bot(command_prefix=f"{PREFIX}",
                   help_command=PrettyHelp(color=discord.colour.Colour.blurple(), show_index=False,
                                           no_category="Chess commands"),
                   intents=intents,
                   case_insensitive=True)

# initialising some global variables
player_list, reacted_list, react_reply_msg_list, registration_started, game_started = [], [], [], False, False

with open("stats.json", "r") as r:
    userdict = json.load(r)


# Start game by creating reaction message
@bot.command()
async def start(ctx):
    """Start a game of chess"""
    global statsdict, msg, channel, registration_started, turn_num, onetwovar, forfeited, game_started, player, board, illegal
    onetwovar = 2
    otmsg = await ctx.send(
        "What mode do you want to play? Respond with 1️⃣ for single player (against stockfish) and "
        "2️⃣ for multiplayer (against a friend).")
    onetwo_list = ["1️⃣", "2️⃣"]
    for rec in onetwo_list:
        await otmsg.add_reaction(rec)

    def onetwo(ms, a):
        return str(ms.emoji) in onetwo_list and a == ctx.author

    try:
        # await ctx.send("got here")
        onetwovar = str(
            (onetwo_list.index(str((await bot.wait_for("reaction_add", check=onetwo, timeout=15))[0].emoji))) + 1)
    except asyncio.TimeoutError:
        await ctx.send("Game cancelled.")
        return

    if onetwovar == "2":
        # await ctx.send("got to two")
        if registration_started or game_started:
            await ctx.send("Only one game can be played at once!")
            return
        msg = await ctx.send(
            "React to this message with <:chess_queen:849232889697796116> to join the game, or :x: to cancel!")
        await msg.add_reaction("<:chess_queen:849232889697796116>")
        await msg.add_reaction("❌")
        registration_started = True
        turn_num = 0
        channel = ctx.message.channel
    elif onetwovar == "1":
        player = ctx.author
        # await ctx.send("got to one")
        engine = chess.engine.SimpleEngine.popen_uci('stockfish.exe')
        white = random.choice([True, False])
        board = chess.Board()
        msg = await ctx.send("What difficulty do you want to play at? React with 1 for easy and 5 for difficult.")
        reaction_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i in reaction_list:
            await msg.add_reaction(i)

        def rcheck(r, a):
            return str(r.emoji) in reaction_list and a == ctx.author

        try:
            reaction, user = await bot.wait_for("reaction_add", check=rcheck, timeout=15)
        except asyncio.TimeoutError:
            await ctx.send("Game cancelled!")
            return
        # await ctx.send("got reaction")
        print(reaction)
        engine.configure({"Skill Level": (reaction_list.index(str(reaction.emoji))) * 2})
        limit = 0.5
        forfeited = False
        game_started = True
        userdict[str(ctx.author.id)]["games"] += 1
        author = ctx.message.guild.get_member(ctx.author.id)

        def check(msgg) -> bool:
            nonlocal ctx
            global illegal
            try:
                board.parse_san(msgg.content)
            except ValueError as ex:
                if "illegal" in str(ex):
                    illegal = True
                check1 = False
            else:
                check1 = True

            return msgg.author == ctx.author and check1

        while board.outcome() is None and white and not forfeited:
            # await ctx.send("got hereeee")
            svg = chess.svg.board(board)
            svg2png(bytestring=svg, write_to='currentsingleboard.png')
            png = discord.File('currentsingleboard.png')
            await ctx.send(file=png, content=f"`{author.display_name}`, it's your turn; you have 60s!")
            try:
                im = await bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                if not forfeited:
                    await ctx.send("Game over! `Stockfish` won by timeout!")
                    userdict[str(ctx.author.id)]["losses"] += 1
                game_started, registration_started = False, False
                return
            await im.add_reaction("✅")
            try:
                board.push_san(im.content)
            except ValueError as e:
                if "illegal" in str(e):
                    await ctx.send("That move is illegal!")

            await ctx.send("The computer is making its move... :thinking:")
            result = engine.play(board, chess.engine.Limit(time=limit))
            board.push(result.move)
            svg = chess.svg.board(board)
            svg2png(bytestring=svg, write_to='currentsingleboard.png')
            png = discord.File('currentsingleboard.png')

        while board.outcome() is None and not white and not forfeited:
            # await ctx.send("got hererr")
            await ctx.send("The computer is making its move... :thinking:")
            result = engine.play(board, chess.engine.Limit(time=limit))
            board.push(result.move)
            svg = chess.svg.board(board, flipped=True)
            svg2png(bytestring=svg, write_to='currentsingleboard.png')
            png = discord.File('currentsingleboard.png')
            await ctx.send(file=png, content=f"`{author.display_name}`, it's your turn; you have 60s!")
            try:
                im = await bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                if not forfeited:
                    await ctx.send("Game over! `Stockfish` won by timeout!")
                    userdict[str(ctx.author.id)]["losses"] += 1
                game_started, registration_started = False, False
                return
            await im.add_reaction("✅")
            board.push_san(im.content)

        if board.outcome().winner is not None:
            svg = chess.svg.board(board) if white else chess.svg.board(board, flipped=True)
            svg2png(bytestring=svg, write_to='currentsingleboard.png')
            png = discord.File('currentsingleboard.png')
            await ctx.send(
                f"Game over! `{'You' if board.outcome().winner == white else 'Stockfish'}` won by {str(board.outcome().termination)[12:]}!",
                file=png)
            userdict[str(ctx.author.id)]["wins" if board.outcome().winner == white else "losses"] += 1
            if board.outcome().winner == white:
                userdict[str(ctx.author.id)]["higheststockfish"] = max(userdict[str(ctx.author.id)]["higheststockfish"],
                                                                       (reaction_list.index(str(reaction.emoji))) * 2)

            game_started, registration_started = False, False

        else:
            svg = chess.svg.board(board)
            svg2png(bytestring=svg, write_to='currentsingleboard.png')
            png = discord.File('currentsingleboard.png')
            await ctx.send(f"Game over! The game was drawn by {str(board.outcome().termination)[12:]}!", file=png)
            game_started, registration_started = False, False
            userdict[str(ctx.author.id)]["draws"] += 1


# initialises bot
@bot.event
async def on_ready():
    global illegal
    await bot.change_presence(activity=discord.Game(name="Chess"))
    print(f"Connected to discord as {bot.user} with {round(bot.latency * 1000, 2)}ms ping.")


# Register players with reaction
@bot.event
async def on_reaction_add(r, a):
    global reacted_list, react_reply_msg_list, registration_started, game_started, board, player_list, msg
    if str(r.emoji) in ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]:
        return
    author = r.message.channel.guild.get_member(a.id)
    if r.message == msg and len(reacted_list) < 2 and not author.bot:
        if str(r.emoji) == "<:chess_queen:849232889697796116>":
            # print(author)
            reacted_list.append(author)
            if "left" in msg.content:
                await react_reply_msg_list[reacted_list.index(author)].edit(
                    content=f"`{author.display_name}` has joined the game!")
            else:
                react_reply_msg_list.append(await channel.send(f"`{author.display_name}` has joined the game!"))
            # print(reacted_list, len(reacted_list))
            if len(reacted_list) == 2:
                await channel.send(
                    f"The game is starting between <@{reacted_list[0].id}> and <@{reacted_list[1].id}>!")
                initgame()
                for i in reacted_list:
                    userdict[str(i.id)]["games"] += 1
                for i in react_reply_msg_list:
                    await i.delete()

                svg = chess.svg.board(board)
                svg2png(bytestring=svg, write_to='currentboard.png')
                svg = discord.File('currentboard.png')
                await channel.send(file=svg,
                                   content=f"Game started! `{player_list[0].display_name}` is starting as white; you "
                                           f"have 60s!")
                if react_reply_msg_list:
                    for i in react_reply_msg_list:
                        await i.delete()
                # try:
                #    await sleep(60)
                #    await r.message.channel.send(f"Game over! <@{player_list[1].id}> has won by timeout!")
                #    registration_started, game_started = False, False
                # except asyncio.CancelledError as e:
                #    print("cancelled error", e)

        elif r.emoji == "❌":
            await msg.edit(content="Game cancelled!")
            registration_started = False
            for i in react_reply_msg_list:
                await i.delete()
            reacted_list, react_reply_msg_list = [], []


@bot.event
async def on_reaction_remove(r, a):
    global react_reply_msg_list, reacted_list
    # print("got here first")
    if str(r.emoji) != "<:chess_queen:849232889697796116>":
        return
    for i in reacted_list:
        if i == await bot.fetch_user(a.id):
            # print("got here")
            index = reacted_list.index(i)
            reacted_list.remove(i)
            mesg = react_reply_msg_list[index]
            await mesg.edit(content=f"{i.display_name} joined the game, then left.")
            print(reacted_list)


@bot.event
async def on_message(inp):
    global registration_started, game_started, turn_num, board, player_list, onetwovar, illegal
    if inp.author.bot:
        return
    if not game_started:
        await bot.process_commands(inp)
        return
    if onetwovar == "2":
        if re.match(r"([KQNBR][a-h][1-8])|([a-h][1-8])|(0-0*)", inp.content) is None:
            await bot.process_commands(inp)
            return
        if inp.author not in player_list and not inp.author.bot:
            return
        if inp.author != player_list[turn_num % 2]:
            await inp.channel.send("It's not your turn!")
            return
        # white is 0, black is 1
        try:
            board.push_san(inp.content)
        except ValueError:
            await inp.channel.send("That move is invalid!")
            return
        # try:
        #    sleep.cancel_all()
        #    await asyncio.wait(sleep.tasks)
        # except ValueError as e:
        #    print("value error ", e)

        await inp.add_reaction("✅")
        if board.outcome() is not None:
            svg = chess.svg.board(board)
            svg2png(bytestring=svg, write_to='currentboard.png')
            svg = discord.File('currentboard.png')

            if board.outcome().winner is None:
                await inp.channel.send(file=svg,
                                       content=f"Game over! The game was drawn by {str(board.outcome().termination)[12:]}!")
                registration_started, game_started = False, False
                for playerr in player_list:
                    userdict[str(playerr.id)]["draws"] += 1
            else:
                winner = player_list[int(board.outcome().winner) + 1].id
                await inp.channel.send(file=svg,
                                       content=f"Game over! <@{winner}> has won by {str(board.outcome().termination)[12:]}!")
                userdict[str(winner)]["wins"] += 1
                userdict[str(player_list[int(board.outcome().winner)].id)]["losses"] += 1
                registration_started, game_started = False, False
        else:
            svg = chess.svg.board(board)
            svg2png(bytestring=svg, write_to='currentboard.png')
            svg = discord.File('currentboard.png')
            await inp.channel.send(file=svg,
                                   content=f"Valid move! {player_list[(turn_num + 1) % 2].display_name}, it's your "
                                           f"turn; "
                                           f"you have 60s!")
        turn_num += 1
    elif onetwovar == "1":
        if illegal:
            await inp.channel.send("That move is illegal!")
            illegal = False
        else:
            await bot.process_commands(inp)
    # try:
    #    await sleep(60)
    #    await inp.channel.send(f"Game over! <@{player_list[turn_num%2].id}> has won by timeout!")
    #    registration_started, game_started = False, False
    # except asyncio.CancelledError as e:
    #    print("cancelled error", e)


@bot.command(aliases=["resign"])
async def forfeit(ctx):
    """Forfeit the game"""
    global player_list, registration_started, game_started, onetwovar, forfeited, player, board

    if onetwovar == "2":
        if ctx.author not in player_list:
            print("wrong author")
            return

        def check(m):
            return m.channel == ctx.channel and m.content in ["y", "yes", "n", "no"]

        await ctx.send("Are you sure you want to forfeit? This will result in a loss! Respond with y/n.")
        try:
            forfeitmsg = await bot.wait_for('message', check=check, timeout=10)
            assert forfeitmsg.content in ["yes", "y"]
        except (asyncio.TimeoutError, AssertionError):
            ctx.send("Forfeit cancelled!")
            return

        svg = chess.svg.board(board)
        svg2png(bytestring=svg, write_to='currentboard.png')
        svg = discord.File('currentboard.png')
        winner = player_list[0] if ctx.author == player_list[1] else player_list[1]
        await ctx.send(file=svg, content=f"Game over! <@{winner.id}> won by forfeit!")
        userdict[str(winner.id)]["wins"] += 1
        userdict[str(ctx.author.id)]["losses"] += 1
        userdict[str(ctx.author.id)]["forfeits"] += 1
        registration_started, game_started = False, False
    elif onetwovar == "1":
        if ctx.author != player:
            return

        def check(m):
            return m.channel == ctx.channel and m.content in ["y", "yes", "n", "no"]

        await ctx.send("Are you sure you want to forfeit? This will result in a loss! Respond with y/n.")
        try:
            forfeitmsg = await bot.wait_for('message', check=check, timeout=10)
            assert forfeitmsg.content in ["yes", "y"]
        except (asyncio.TimeoutError, AssertionError):
            ctx.send("Forfeit cancelled!")
            return
        svg = chess.svg.board(board)
        svg2png(bytestring=svg, write_to='currentsingleboard.png')
        png = discord.File('currentsingleboard.png')
        await ctx.send(file=png, content="Game over! `Stockfish` won by forfeit!")
        userdict[str(ctx.author.id)]["forfeits"] += 1
        userdict[str(ctx.author.id)]["losses"] += 1

        forfeited = True


@bot.command()
async def draw(ctx):
    """Request a draw"""
    global player_list, registration_started, game_started
    if ctx.author not in player_list:
        print("wrong author")
        return
    confirm = player_list[0] if ctx.author == player_list[1] else player_list[1]

    def check(m):
        nonlocal confirm
        return m.author == confirm and m.channel == ctx.channel and m.content in ["y", "yes", "n", "no"]

    ctx.send(f"<@{confirm.id}>, do you accept the draw?")
    try:
        mesg = await bot.wait_for('message', check=check, timeout=10)
        assert mesg.content in ["yes", "y"]
    except (asyncio.TimeoutError, AssertionError):
        ctx.send("Draw rejected!")
        return

    svg = chess.svg.board(board)
    svg2png(bytestring=svg, write_to='currentboard.png')
    svg = discord.File('currentsingleboard.png')
    await ctx.send(file=svg, content=f"Game over! The game was drawn!")
    userdict[str(ctx.author.id)]["draws"] += 1
    userdict[str(confirm.id)]["losses"] += 1
    registration_started, game_started = False, False


@bot.command()
async def stats(ctx, arg=None):
    embed = discord.Embed(colour=discord.Colour.blurple())
    if arg is None:
        user = ctx.author
    else:
        if "<@" in arg:
            user = bot.fetch_user(arg[3:-2])
        else:
            try:
                user = arg
                for i in userdict:
                    if user == userdict[i]["name"]:
                        raise ValueError
            except ValueError:
                user = await bot.fetch_user(i)
            else:
                await ctx.send("Invalid user, defaulting to you!")
                user = ctx.author

    dict = userdict[str(user.id)]
    embed.set_author(name=f"{user.name}'s stats")
    embed.add_field(name="Wins", value=dict["wins"])
    embed.add_field(name="Losses", value=dict["losses"])
    embed.add_field(name="Forfeits (counted in losses)", value=dict["forfeits"])
    embed.add_field(name="Draws", value=dict["draws"])
    embed.add_field(name="Games played", value=dict["games"])
    embed.add_field(name="Win/loss ratio",
                    value=(round(dict["wins"] / dict["losses"], 3)) if dict["losses"] > 0 else dict["wins"])
    embed.add_field(name="Highest level of stockfish beat", value=dict["higheststockfish"])
    await ctx.send(embed=embed)


@bot.command(aliases=["lb"])
async def leaderboard(ctx, arg="wins"):
    statist = {}
    statisticwl = {}
    embed = discord.Embed(colour=discord.Colour.blurple())
    embed.set_author(name=f'{arg if arg not in ["wl", "w/l", "winloss", "win/loss"] else "win/loss"} leaderboard')
    if arg == "loss":
        arg = "losses"
    elif arg[-1] != "s" and arg not in ["wl", "w/l", "winloss", "win/loss"]:
        arg += "s"
    for i in userdict:
        if arg not in ["wl", "w/l", "winloss", "win/loss"]:
            statist[i] = userdict[i][arg]
        statisticwl[i] = ([userdict[i]["wins"] / userdict[i]["losses"]] if userdict[i]["losses"] > 0 else userdict[i]["wins"])
    for j in range(5):
        print(statist)
        mx = max(statist if arg not in ["wl", "w/l", "winloss", "win/loss"] else statisticwl, key=statist.get if arg not in ["wl", "w/l", "winloss", "win/loss"] else statisticwl.get)
        embed.add_field(name=(await bot.fetch_user(mx)).name, value=statist[str(mx)] if arg not in ["wl", "w/l", "winloss", "win/loss"] else statisticwl[str(mx)], inline=False)
        statist.pop(str(mx)) if arg not in ["wl", "w/l", "winloss", "win/loss"] else statisticwl.pop(str(mx))
    await ctx.send(embed=embed)


@bot.command()
async def save(ctx):
    saver()
    await ctx.send("Saved!")


def initgame():
    global board, game_started, player_list, turn_num
    game_started = True
    random.shuffle(reacted_list)
    player_list = [reacted_list[0], reacted_list[1]]
    board = chess.Board()
    turn_num = 0


def saver():
    with open("stats.json", "w") as w:
        json.dump(userdict, w)
    print("saved file.")


rt = RepeatedTimer(60, saver)
bot.run(TOKEN)
