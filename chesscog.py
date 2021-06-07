"""Chess commands"""
# standard classes
import asyncio
import json
import random
from io import BytesIO
# external classes
from typing import Any, Union
import chess
import chess.engine
import chess.svg
import numpy as np
from cairosvg import svg2png
from discord.ext import commands
# custom classes
import config
import othercog
from player import *

# declare global variables at module level
status = Status.NULL
playerlist: dict = config.playerlist
illegal: tuple[bool, Union[discord.Message, None]] = False, None


class Chess(commands.Cog):
    """The main cog for chess self.bot."""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Carry out initialisation tasks on connection to discord."""
        global playerlist, status
        status = Status.NULL  # set default status
        # load json of users
        with open("stats.json", "r") as f:
            userdict = json.load(f)
        playerlist = {}
        # create player object list
        for i in userdict:
            u = await self.bot.fetch_user(i)
            player = Player(user=u, userdict=userdict)
            playerlist[str(player.id)] = player
            print(player.id, player)
        config.playerlist = playerlist

    @commands.Cog.listener()
    async def on_message(self, msg) -> None:  # to listen for illegal moves
        global illegal
        if illegal[0] and msg == illegal[1]:
            await msg.channel.send("That move is illegal!")
            await msg.add_reaction("❌")
            illegal = False, None

    @commands.command()
    async def start(self, ctx) -> None:
        """Start a game of chess."""
        global status, playerlist

        if status != Status.NULL:  # game has already started / up for joining
            await ctx.send("Only one game may be played at a time!")
            return

        status = Status.REGISTRATION
        playerlist = config.playerlist
        player = playerlist[str(ctx.author.id)]
        try:
            mode = Mode(await self.get_mode(ctx))
        except Cancelled as e:
            print(e)
            return
        except KeyError as e:
            print(e)
            await ctx.send("I'm not done initialising yet!")
            status = Status.NULL
            return

        # singleplayer
        if mode == Mode.SINGLE:
            # initialise game
            try:
                player.games += 1  # increase games played
                await self.init_single(ctx, player, await self.get_difficulty(ctx))  # set skill to user reaction
            except Cancelled as e:  # game cancelled
                print(e)
                return

        # multiplayer
        elif mode == Mode.MULTI:
            # initialise game
            try:
                await self.init_multi(ctx, await self.get_players(ctx))
            except Cancelled as e:
                print(e)
                return

    @commands.command(aliases=["resign", "giveup", "lose"])
    async def forfeit(self, ctx) -> None:
        """Immediately end the game with a loss."""
        global status

        # forfeit confirmation checker
        def check(m):
            return m.content in ["y", "yes", "n", "no"] and m.author == ctx.author

        # does not respond to bots
        if ctx.author.bot:
            return
        player = playerlist[str(ctx.author.id)]

        # not playing
        if player.mode == Mode.NULL:
            await ctx.send("You aren't in a game!")
            return

        # confirm forfeit
        await ctx.send("Are you sure you want to forfeit? This will result in a loss! Respond with y/n.")
        try:
            forfeitmsg = await self.bot.wait_for('message', check=check, timeout=10)
            assert forfeitmsg.content in ["yes", "y"]
        except (asyncio.TimeoutError, AssertionError):  # assert error means No, timeout error means no response.
            ctx.send("Forfeit cancelled!")
            return

        # forfeit is confirmed

        # singleplayer
        if player.mode == Mode.SINGLE:
            await ctx.send(f"Game over! `Stockfish` won by forfeit!")
            player.mode = Mode.NULL
            status = Status.NULL
            othercog.Other.save([player])

            # update stats
            player.losses += 1
            player.forfeits += 1

        # multiplayer
        if player.mode == Mode.MULTI:
            winner = player.opponent
            await ctx.send(f"Game over! {winner.mention} won by forfeit!")

            player.mode, winner.mode = Mode.NULL, Mode.NULL
            status = Status.NULL
            # update stats
            winner.wins += 1
            player.losses += 1
            player.forfeits += 1

    async def init_single(self, ctx, player: Player, skill: int) -> None:
        """Initialise singleplayer game - create engine, board, player."""

        # create default empty chessboard
        board = chess.Board()

        # create stockfish engine with skill level of skill parameter
        engine = chess.engine.SimpleEngine.popen_uci('stockfish.exe')
        engine.configure({"Skill Level": skill})

        # assign player gameplay attributes
        player.mode = Mode(1)
        player.chesscolor = Color(random.choice([True, False]))

        # start main gameplay loop
        await self.gameplay_single(ctx, player, board, engine, skill)

    async def gameplay_single(self, ctx, player: Player, board: chess.Board, engine: chess.engine.SimpleEngine,
                              skill: int, timelimit: int = 0.5, ) -> None:
        """Main singleplayer gameplay loop."""

        temp: Any = None  # dummy variable to process unpack here

        if player.chesscolor == Color.WHITE:  # if player is white
            await ctx.send(file=await self.send_svg(board, player),
                           content=f"`{ctx.guild.get_member(player.id).display_name}`, it's your turn; you have 60s!")
            board, player, temp = await self.player_move(ctx, board, player)  # player moves first

        while player.mode == Mode.SINGLE and board.outcome() is None:
            board, player = await self.engine_move(ctx, board, engine, timelimit,
                                                   player)  # engine moves 2nd if player is white, else moves first
            if not (board.outcome() is None and player.mode == Mode.SINGLE):
                break
            await ctx.send(file=await self.send_svg(board, player),
                           content=f"`{ctx.guild.get_member(player.id).display_name}`, it's your turn; you have 60s!")
            board, player, temp = await self.player_move(ctx, board, player)  # player always follows engine

        if board.outcome() is not None:  # game has ended by chess.Termination
            if board.outcome().winner is None:  # draw
                await ctx.send(f"Game over! The game was drawn by {board.outcome().termination.name}", file=await self.send_svg(board, player))
                player.draws += 1
                player.mode = Mode.NULL

            elif board.outcome().winner == player.chesscolor.value:  # player won
                await ctx.send(f"Game over! {player.mention} won by {board.outcome().termination.name}!", file=await self.send_svg(board, player))
                player.wins += 1
                player.stockfish = max(player.stockfish, skill)
                player.mode = Mode.NULL  # player is not in a game anymore

            else:  # player lost
                await ctx.send(f"Game over! `Stockfish` won by {board.outcome().termination.name}!", file=await self.send_svg(board, player))
                player.losses += 1
                player.mode = Mode.NULL

            othercog.Other.save([player]) # update stats file

    async def init_multi(self, ctx, player_list: list) -> None:
        """Initialise multiplayer game - create board, players."""

        # create default empty chessboard
        board = chess.Board()

        # color array
        randarray = [Color.WHITE, Color.BLACK]

        # random player array
        random.shuffle(player_list)

        # assign black and white
        for player in player_list:
            player.mode = Mode(2)
            player.opponent = np.setdiff1d(player_list, [player])[0]
            player.chesscolor = randarray[player_list.index(player)]

        # start main gameplay loop
        await self.gameplay_multi(ctx, player_list, board)

    # TODO: Test & Fix multiplayer
    async def gameplay_multi(self, ctx, player_list: list, board: chess.Board):
        """Main gameplay loop for multiplayer."""

        # reassign player objects to variables with color names (for convenience)
        white: Player = player_list[0]
        black: Player = player_list[1]

        while board.outcome() is None and white.mode == Mode.MULTI and black.mode == Mode.MULTI:
            board, white, player_list = await self.player_move(ctx, board, white, player_list)
            if not (board.outcome() is None and white.mode == Mode.MULTI and black.mode == Mode.MULTI):
                break
            board, black, player_list = await self.player_move(ctx, board, black, player_list)

        oc = board.outcome()
        if oc.winner:  # has winner
            winner: Player = white if oc.winner == white.chesscolor else black  # get player on same side as winner i.e. the winner
            loser: Player = white if oc.winner != white.chesscolor else black
            await ctx.send(f"Game over! {winner.mention} won by {oc.termination.name}!")  # announce winner

            # update player stats
            winner.wins += 1
            loser.losses += 1
            winner.mode, loser.mode = Mode.NULL, Mode.NULL

            # save stats
            othercog.Other.save([winner, loser])
        else:
            await ctx.send(f"Game over! The game was drawn by {oc.termination.name}!")

            # update player stats
            for i in player_list:
                i.draws += 1
                i.mode = Mode.NULL

            # save stats
            othercog.Other.save(player_list)

    async def engine_move(self, ctx, board, engine, timelimit, player):
        await ctx.send("The computer is thinking... :thinking:")
        board.push(engine.play(board, chess.engine.Limit(
            time=timelimit)).move)  # get engine move based on board, limit from param


        return board, player

    async def player_move(self, ctx, board: chess.Board, player: Player, player_list: list = None) -> (
            chess.Board, Player, dict):
        """Get player move and add it to the move stack. Non mode-dependant"""
        global status

        def check_san(m: discord.Message) -> bool:
            """Input (SAN) validity checker"""
            global illegal
            try:
                board.parse_san(m.content)  # check if move is legal
            except ValueError as ve:
                print(ve)
                if "illegal" in str(ve) and not m.author.bot and m.author == ctx.author:
                    illegal = (True, m)
                return False
            return True and m.author.id == player.id

        try:
            msg = await self.bot.wait_for("message", check=check_san, timeout=60)
        except asyncio.TimeoutError:
            # game ended
            if player.mode == Mode.NULL:
                return board, player, player_list
            status = Status.NULL
            # singleplayer
            if player.mode == Mode.SINGLE:
                await ctx.send("Game over! `Stockfish` won by timeout!")
                player.mode = Mode.NULL
                player.losses += 1

                othercog.Other.save([player])
            # multiplayer
            elif player.mode == Mode.MULTI:
                winner = player.opponent
                # winner is winner, player is loser
                await ctx.send(f"Game over! {ctx.guild.get_member(winner.id).display_name} won by timeout!")
                winner.wins += 1
                winner.mode = Mode.NULL
                player.losses += 1
                player.mode = Mode.NULL

                othercog.Other.save([winner, player])
            return board, player, player_list
        try:
            board.push_san(msg.content)
        except Exception as e:
            print(e)

        if player.mode == Mode.MULTI:
            other = np.setdiff1d(player_list, [player])[0]
            await ctx.send(f"`{ctx.guild.get_member(other.id).display_name}`, it's your turn; you have 60s!",
                           file=await self.send_svg(board, other))

        return board, player, player_list

    async def react(self, reaction_list: list[str], msg: discord.Message) -> None:
        for i in reaction_list:
            await msg.add_reaction(i)

    async def get_difficulty(self, ctx) -> int:
        """Get difficulty via reactions (1-5 reaction translated to 0,2,4,6,8 stockfish skill level)"""

        # create message to react to
        msg = await ctx.send("What difficulty do you want to play at? React with 1️⃣ for easy and 5️⃣ for difficult.")
        reaction_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]  # list of valid reactions

        # reaction check function
        def check(r, a):
            return str(
                r.emoji) in reaction_list and a == ctx.author  # checks if the emoji is part of 1-5 and is sent by the player

        try:  # get reaction to evaluate difficulty
            await self.react(reaction_list, msg)
            reaction, reactionuser = await self.bot.wait_for("reaction_add", check=check, timeout=15)
        except asyncio.TimeoutError:  # cancel game after 15s of no response
            await ctx.send("Game cancelled!")
            raise Cancelled("Timeout on difficulty")  # surround this function with try except to cancel game

        return (reaction_list.index(str(reaction.emoji))) * 2

    async def get_mode(self, ctx) -> int:
        """get mode via reactions (1,2) - see Mode enum"""
        msg = await ctx.send("What mode do you want to play? React with 1️⃣ for singleplayer and 2️⃣ for multiplayer.")
        reaction_list = ["1️⃣", "2️⃣"]

        # reaction check function
        def check(r, a):
            return str(r.emoji) in reaction_list and a == ctx.author

        try:  # get reaction to evaluate difficulty
            await self.react(reaction_list, msg)
            reaction, reactionuser = await self.bot.wait_for("reaction_add", check=check, timeout=15)
        except asyncio.TimeoutError:  # cancel game after 15s of no response
            await ctx.send("Game cancelled!")
            raise Cancelled("Timeout on mode")  # Surround with try except to cancel game

        return reaction_list.index(str(reaction.emoji)) + 1

    async def get_players(self, ctx) -> list:
        """Get list of player via reactions"""

        # Reaction checker
        def check(r, a):
            return str(r.emoji) in reaction_list  # only respond to emojis in the reaction list

        msg = await ctx.send(
            "React to this message with <:chess_queen:849232889697796116> to join the game, or :x: to cancel!")
        reaction_list = ["<:chess_queen:849232889697796116>", "❌"]
        reactions = []  # list of players who reacted
        await self.react(reaction_list, msg)  # asynchronously add reactions to message

        for i in range(2):  # 2 players
            ra = (await self.bot.wait_for("reaction_add", check=check, timeout=60))[0]  # get tuple of reaction, user
            if str(ra[0].emoji) == "❌":  # cancel trigger
                await ctx.send("Game cancelled!")
                raise Cancelled  # surround with try except to cancel game
            reactions.append(playerlist[ra[1].id])  # get player from author id

        return reactions  # list of player objects that are in this game

    async def send_svg(self, board: chess.Board, player: Player) -> discord.File:
        """Method to create a discord File from a png image from the chess board."""
        png = BytesIO()
        bstring = chess.svg.board(board, flipped=not player.chesscolor.value)
        svg2png(bytestring=bstring, write_to=png)

        png.seek(0)
        return discord.File(png, filename="board.png")
