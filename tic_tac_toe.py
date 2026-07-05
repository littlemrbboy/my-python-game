"""
TIC-TAC-TOE (GUI VERSION)
Uses tkinter — Python's built-in library for making windows, buttons, etc.
Nothing extra to install; tkinter comes bundled with Python.

Structure of this program:
1. A start screen with two buttons: "Play vs Computer" and "Play vs Human"
2. A game screen: a 3x3 grid of buttons acting as the board
3. A "Play Again" button once the game ends

Since this is event-driven (things happen when you CLICK, not in a straight
line top-to-bottom), the code is organized as functions that get called
by button clicks, rather than one long sequence like the console version.
"""

import tkinter as tk
from tkinter import font
import random

# ---------------------------------------------------------
# GAME STATE
# ---------------------------------------------------------

# These variables are shared across functions, so we declare them here
# and update them as the game progresses.

board = [" "] * 9               # same idea as the console version: 9 squares
buttons = []                    # will hold the actual button widgets, one per square
mode = None                     # "computer" or "human"
current_symbol = "X"            # whose turn it is right now
player_symbol = "X"             # only used in "computer" mode
computer_symbol = "O"           # only used in "computer" mode
game_over = False


WINNING_COMBINATIONS = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
    [0, 3, 6], [1, 4, 7], [2, 5, 8],  # columns
    [0, 4, 8], [2, 4, 6]              # diagonals
]


# ---------------------------------------------------------
# GAME LOGIC (same ideas as the console version)
# ---------------------------------------------------------

def is_winner(symbol):
    for a, b, c in WINNING_COMBINATIONS:
        if board[a] == symbol and board[b] == symbol and board[c] == symbol:
            return True
    return False


def is_board_full():
    return " " not in board


def get_available_moves():
    return [i for i in range(9) if board[i] == " "]


def find_winning_move(symbol):
    """Same trick as before: try each empty square, see if it wins, undo it."""
    for move in get_available_moves():
        board[move] = symbol
        if is_winner(symbol):
            board[move] = " "
            return move
        board[move] = " "
    return None


def get_computer_move():
    """Decide where the computer should play: win > block > random."""
    winning_move = find_winning_move(computer_symbol)
    if winning_move is not None:
        return winning_move

    blocking_move = find_winning_move(player_symbol)
    if blocking_move is not None:
        return blocking_move

    return random.choice(get_available_moves())


# ---------------------------------------------------------
# UI SETUP
# ---------------------------------------------------------
root = tk.Tk()
root.title("Tic-Tac-Toe")
root.resizable(False, False)

big_font = font.Font(size=32, weight="bold")
label_font = font.Font(size=14)

# This frame holds whatever screen is currently showing.
# We destroy and rebuild its contents when switching screens
# (start screen <-> game screen).
main_frame = tk.Frame(root, padx=20, pady=20)
main_frame.pack()

status_label = tk.Label(main_frame, text="", font=label_font)


def clear_screen():
    """Removes everything currently shown, so we can build a new screen."""
    for widget in main_frame.winfo_children():
        widget.destroy()


# ---------------------------------------------------------
# START SCREEN
# ---------------------------------------------------------
def show_start_screen():
    clear_screen()

    title = tk.Label(main_frame, text="Tic-Tac-Toe", font=("Arial", 24, "bold"))
    title.pack(pady=(0, 20))

    vs_computer_btn = tk.Button(
        main_frame, text="Play vs Computer", font=label_font,
        width=20, height=2, command=lambda: start_game("computer")
    )
    vs_computer_btn.pack(pady=5)

    vs_human_btn = tk.Button(
        main_frame, text="Play vs Human", font=label_font,
        width=20, height=2, command=lambda: start_game("human")
    )
    vs_human_btn.pack(pady=5)


# ---------------------------------------------------------
# GAME SCREEN
# ---------------------------------------------------------
def start_game(chosen_mode):
    """Called when a mode button is clicked. Sets up a fresh game."""
    global mode, board, buttons, current_symbol, player_symbol, computer_symbol, game_over

    mode = chosen_mode
    board = [" "] * 9
    game_over = False

    # Randomly assign symbols, X always goes first
    player_symbol = random.choice(["X", "O"])
    computer_symbol = "O" if player_symbol == "X" else "X"
    current_symbol = "X"

    show_game_screen()

    # If it's vs-computer and the computer happens to be X, it moves first
    if mode == "computer" and current_symbol == computer_symbol:
        root.after(400, computer_turn)  # small delay so it feels natural


def show_game_screen():
    clear_screen()
    global buttons, status_label

    if mode == "computer":
        status_text = f"You are {player_symbol} | Computer is {computer_symbol}"
    else:
        status_text = "Player X and Player O — take turns!"

    status_label = tk.Label(main_frame, text=status_text, font=label_font)
    status_label.pack(pady=(0, 10))

    turn_label_text = f"{current_symbol}'s turn"
    global turn_label
    turn_label = tk.Label(main_frame, text=turn_label_text, font=label_font, fg="blue")
    turn_label.pack(pady=(0, 10))

    grid_frame = tk.Frame(main_frame)
    grid_frame.pack()

    buttons = []
    for i in range(9):
        btn = tk.Button(
            grid_frame, text=" ", font=big_font, width=3, height=1,
            command=lambda index=i: on_square_click(index)
        )
        btn.grid(row=i // 3, column=i % 3, padx=3, pady=3)
        buttons.append(btn)

    back_btn = tk.Button(main_frame, text="Back to Menu", command=show_start_screen)
    back_btn.pack(pady=(15, 0))


def update_turn_label():
    turn_label.config(text=f"{current_symbol}'s turn")


def on_square_click(index):
    """Called whenever a board square button is clicked."""
    global current_symbol, game_over

    if game_over or board[index] != " ":
        return  # ignore clicks on taken squares or after the game has ended

    # If it's vs-computer mode, don't let the player click during the computer's turn
    if mode == "computer" and current_symbol == computer_symbol:
        return

    place_symbol(index, current_symbol)

    if check_game_end():
        return

    switch_turn()

    # If it's now the computer's turn, let it move after a short delay
    if mode == "computer" and current_symbol == computer_symbol and not game_over:
        root.after(400, computer_turn)


def computer_turn():
    """Runs the computer's move, then checks for game end."""
    global game_over
    if game_over:
        return

    move = get_computer_move()
    place_symbol(move, current_symbol)

    if check_game_end():
        return

    switch_turn()


def place_symbol(index, symbol):
    """Updates both the data (board list) and the visual button text."""
    board[index] = symbol
    buttons[index].config(text=symbol, disabledforeground="black")


def switch_turn():
    global current_symbol
    current_symbol = "O" if current_symbol == "X" else "X"
    update_turn_label()


def check_game_end():
    """Checks for a win or draw. If the game is over, shows the result."""
    global game_over

    if is_winner(current_symbol):
        game_over = True
        if mode == "computer":
            if current_symbol == player_symbol:
                message = "🎉 You win!"
            else:
                message = "💻 Computer wins!"
        else:
            message = f"🎉 Player {current_symbol} wins!"
        show_result(message)
        return True

    if is_board_full():
        game_over = True
        show_result("It's a draw!")
        return True

    return False


def show_result(message):
    """Displays the win/draw message and a 'Play Again' button."""
    turn_label.config(text=message, fg="green")

    play_again_btn = tk.Button(
        main_frame, text="Play Again", font=label_font,
        command=lambda: start_game(mode)
    )
    play_again_btn.pack(pady=(15, 0))


# ---------------------------------------------------------
# START THE APP
# ---------------------------------------------------------

show_start_screen()
root.mainloop()  # This line keeps the window open and listening for clicks.
                   # Nothing after this line will run until the window is closed.