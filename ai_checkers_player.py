"""
AI Checkers Player

A Python checkers player that uses Google's GenAI API to choose from
precomputed legal moves while enforcing game rules such as mandatory jumps,
multi-jump completion, king promotion, and opponent move validation.

Install dependency:
    pip install -q -U google-genai
"""
import warnings
warnings.filterwarnings("ignore")

import ast
import sys
import select
import time
import re
from google import genai
from google.genai import types

class CheckersPlayer:
    '''A class that represents a player in a game of checkers'''

    def __init__(self, color, gemma_key=None, team_name="ai_checkers_player"):
        self.color = color.upper()
        self.opp_color = 'RED' if self.color == 'BLACK' else 'BLACK'
        self.gemma_key = gemma_key
        self.client = None

        self.move_count = 0  # Track total moves
        self.move_without_capture = 0 # Tracks consecutive moves without captures for draw limit

        # Initialize AI client and config
        if self.gemma_key:
            self.client = genai.Client(api_key=self.gemma_key)

            # Define strict instructions for the AI's behavior
            system_instructions = (
                f"You are playing checkers. You are player {self.color}. "
                f"Valid pieces to move are {self.color}. "
                "Determine the absolute best move. "
                "CRITICAL INSTRUCTION: Output your move as a sequence of coordinates. "
                "For a standard move, output two coordinates (e.g., '21 30'). "
                "For a multi-jump, output all coordinates in the chain (e.g., '63 41 23'). "
                "DO NOT output any other words, letters, or punctuation."
            )

            # Setup the config with MINIMAL thinking level 
            self.ai_config = types.GenerateContentConfig(
                system_instruction=system_instructions,
                thinking_config=types.ThinkingConfig(thinking_level="minimal") 
            )

        self.board = [[None for _ in range(8)]for _ in range(8)]
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 != 0:
                    if row < 3: self.board[row][col] = 'BLACK'
                    elif row > 4: self.board [row][col] = 'RED'

    def print_board(self):
        '''Visualizes the board for the human and the AI'''
        print("\n     0    1    2    3    4    5    6    7")
        for i, row in enumerate(self.board):
            row_disp = []
            for p in row:
                if p is None: row_disp.append(".")
                elif "KING" in p: row_disp.append(p[0].upper() + "K") # BK or RK
                else: row_disp.append(p[0].upper()) # B or R

            # Format the row to align with the numbers
            formatted_row = "".join(f"{piece:>5}" for piece in row_disp)
            print(f"{i}{formatted_row}")

    def check_game_over(self):
        '''Checks if either player has run out of pieces or if a draw is reached'''
        # Check for draw condition first
        if self.move_without_capture >= 20:
            return "DRAW"

        my_pieces = 0
        opp_pieces = 0

        for row in self.board:
            for p in row:
                if p is not None:
                    if self.color in p:
                        my_pieces += 1
                    else:
                        opp_pieces += 1

        # Win/loss conditions
        if my_pieces == 0:
            return "LOSS"
        if opp_pieces == 0:
            return "WIN"

        return None

    def piece_can_jump(self, r, c, color, is_king, current_board):
        '''Checks if a specific piece at (r, c) can make a jump on the given board state'''
        opp_color = 'RED' if color == 'BLACK' else 'BLACK'
        directions = []
        if color == 'BLACK' or is_king:
            directions.extend([(2, 2), (2, -2)])
        if color == 'RED' or is_king:
            directions.extend([(-2, 2), (-2, -2)])

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            mid_r, mid_c = r + (dr // 2), c + (dc // 2)

            if 0 <= nr < 8 and 0 <= nc < 8:
                if current_board[nr][nc] is None:
                    mid_piece = current_board[mid_r][mid_c]
                    if mid_piece and opp_color in mid_piece:
                        return True
        return False
    
    # Depth-first search (DFS) to calculate complete multi-jump paths
    def get_all_valid_moves(self, color):
        opp_color = 'RED' if color == 'BLACK' else 'BLACK'
        jumps = []
        normal_moves = []

        def get_jumps_from (r, c, is_king, current_board, current_path):
            found_further_jump = False
            jump_directions = []
            if color == 'BLACK' or is_king:
                jump_directions.extend([(2, 2), (2, -2)])
            if color == 'RED' or is_king:
                jump_directions.extend([(-2, 2), (-2, -2)])
            
            for dr, dc in jump_directions:
                nr, nc = r + dr, c + dc
                mid_r, mid_c = r + (dr // 2), c + (dc // 2)
                if 0 <= nr < 8 and 0 <= nc < 8:
                    if current_board[nr][nc] is None:
                        mid_piece = current_board[mid_r][mid_c]
                        if mid_piece and opp_color in mid_piece:
                            found_further_jump = True

                            # Simulate the jump on a temporary board
                            new_board = [row.copy() for row in current_board]
                            new_board[nr][nc] = current_board[r][c]
                            new_board[r][c] = None
                            new_board[mid_r][mid_c] = None

                            new_path = current_path + [f"{nr}{nc}"]

                            #Check if piece gets kinged mid_jump (which ends the turn immediately)

                            became_king = False
                            if not is_king:
                                if (color == 'BLACK' and nr ==7) or (color == 'RED' and nr == 0):
                                    became_king = True
                                    new_board[nr][nc] = f"{color}_KING"
                            
                            if became_king:
                                jumps.append(" ".join(new_path))
                            else:
                                # Recursively check for the next jump in the chain
                                get_jumps_from(nr, nc, is_king, new_board, new_path)

            # If no more jumps are found from this spot, add the completed path to our list
            if not found_further_jump and len(current_path) > 1:
                jumps.append(" ".join(current_path))

        # Scan the board for all our pieces
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece and color in piece: 
                    is_king = 'KING' in piece

                    # 1. Search for deep jump paths
                    get_jumps_from(r, c, is_king, self.board, [f"{r}{c}"])

                    # 2. Grab standard single-step moves just in case
                    move_directions = []
                    if color == 'BLACK' or is_king:
                        move_directions.extend([(1, 1), (1, -1)])
                    if color == 'RED' or is_king:
                        move_directions.extend([(-1, 1), (-1, -1)])

                    for dr, dc in move_directions:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 8 and 0 <= nc < 8:
                            if self.board[nr][nc] is None:
                                normal_moves.append(f"{r}{c} {nr}{nc}")

        # If any jump exists anywhere, checkers rules say we MUST take one of them
        if jumps:
            return jumps, True
        return normal_moves, False  

    def _get_instructions(self):
        '''Constructs the prompt with strict rules and pre-calculated moves'''
        board_lines = ["     0    1    2    3    4    5    6    7"] # Edited for visually-appealing board for player
        for i, row in enumerate(self.board):
            row_disp = []
            for p in row:
                if p is None: row_disp.append(".")
                elif "KING" in p: row_disp.append(p[0].upper() + "K")
                else: row_disp.append(p[0].upper())
            formatted_row = "".join(f"{piece:>5}" for piece in row_disp)
            board_lines.append(f"{i}{formatted_row}")
        board_txt = "\n".join(board_lines)

        valid_steps, must_jump = self.get_all_valid_moves(self.color)
        
        instructions = (
            f"You are playing checkers. You are player {self.color}.\n"
            f"The current state of the board is:\n{board_txt}\n\n"
        )

        # Give the AI the complete set of legal move paths
        if must_jump:
            instructions += f"*** CRITICAL: MANDATORY JUMP AVAILABLE! ***\n"
            instructions += f"You MUST capture an opponent's piece. Here are your FULL, valid jump chains: {', '.join(valid_steps)}\n"
            instructions += "You must pick exactly ONE of those chains and output its coordinates exactly as shown. \n"
        else:
            instructions += f"Here is a list of all legal standard moves you can choose from: {', '.join(valid_steps)}\n"
            instructions += "Select the best strategic move from this list and output its coordinates. \n"

        instructions += (
            "\nOutput ONLY your chosen coordinate sequence.\n"
            "DO NOT output any explanations, punctuation, or extra words."
        )
        return instructions

    def make_move(self, seconds_remaining):
        '''Requests move from the AI autonomously'''
        print(f"\n--- Your Turn ({self.color}) ---")
        self.print_board()

        if not self.client:
            print("ERROR: AI is not initialized. An API key is required for autonomous play.")
            sys.exit(1)

        instructions = self._get_instructions()

        # Allowing the AI 15 attempts to correct its path
        for attempt in range(15):
            try:
                response = self.client.models.generate_content(
                    model="gemma-4-26b-a4b-it",
                    contents=instructions,
                    config=self.ai_config
                )
                
                ai_text = response.text.strip() if response.text else ""
                print(f"[AI Attempt {attempt+1}]: {ai_text}")
                
                # Parse only valid board coordinates like "21 30" or "63 41 23"
                coords = re.findall(r'\b[0-7][0-7]\b', ai_text)
                move = [(int(coord[0]), int(coord[1])) for coord in coords]

                if len(move) < 2:
                    instructions += f"\nFORMAT ERROR: Could not parse '{ai_text}'. Output at least two coordinates like '21 30'."
                    continue

                # Force the AI to choose one of the actual legal moves
                valid_moves, must_jump = self.get_all_valid_moves(self.color)
                move_str = " ".join(f"{r}{c}" for r, c in move)

                if move_str not in valid_moves:
                    # GEMINI FIX: If AI only outputs part of a multi-jump, auto-complete it
                    matches = [v for v in valid_moves if v.startswith(move_str)]
                    if len(matches) == 1:
                        print(f"[Auto-Correct] Extending AI's partial move '{move_str}' to full jump '{matches[0]}'")
                        move_str = matches[0]
                        # Rebuild move list from the corrected string
                        coords = move_str.split()
                        move = [(int(c[0]), int(c[1])) for c in coords]
                    else:
                        instructions += (
                            f"\nINVALID MOVE: '{move_str}' is incomplete or illegal. "
                            f"You MUST choose EXACTLY ONE complete move from this list: {', '.join(valid_moves)}"
                        )
                        continue

                # Validate the move using existing logic
                good_move = self.move_and_captures_if_good(move, self.color)
            
                if good_move:
                    captures = good_move[1]

                    # Execute valid move
                    moving = self.board[move[0][0]][move[0][1]]
                    self.board[move[0][0]][move[0][1]] = None
                    for capture in captures:
                        self.board[capture[0]][capture[1]] = None
                
                    # Kinging logic
                    end_r = move[-1][0]
                    if (moving == 'BLACK' and end_r == 7) or (moving == 'RED' and end_r == 0):                    
                        moving = f"{moving}_KING"
                        print(f"PROMOTION! The AI piece is now a KING.")

                    self.board[move[-1][0]][move[-1][1]] = moving
                    self.move_count += 1

                    # Draw counter logic
                    if len(captures) > 0:
                        self.move_without_capture = 0
                    else:
                        self.move_without_capture += 1

                    # Print the exact move sequence for an external match runner to read
                    print(move) 
                    return good_move
                else:
                    instructions += f"\nINVALID MOVE: '{ai_text}' was rejected. If this is a multi-jump, you MUST include ALL landing coordinates in the chain! Otherwise, pick a different valid move from the list."
                    
            except Exception as e:
                # Catch rate limits or crashes, print them, and pause for 2 seconds to recover
                print(f"\n[API WARNING]: {e}. Pausing for 2 seconds to prevent rate-limiting...")
                time.sleep(2)
                continue

        print("FATAL: AI failed to make a valid move after 15 attempts. Forfeiting match.")
        sys.exit(1)

    def move_and_captures_if_good(self, move, color):
        if len(move) < 2:
            print('NOT ENOUGH MOVES')
            return False
        start = move[0]
        if start[0] < 0 or start[0] > 7 or start[1] < 0 or start[1] > 7:
            print(start, 'is not on the board')
            return False
            
        # BUG FIX: Ensure the square is not empty before checking if it belongs to the player
        start_piece = self.board[start[0]][start[1]]
        if start_piece is None or color not in start_piece:
            print('Cannot move from', start, 'as', color)
            return False

        piece_moving = self.board[move[0][0]][move[0][1]]
        king_moving = 'KING' in piece_moving
        color_moving = 'RED' if 'RED' in piece_moving else 'BLACK'
        opp_color = 'BLACK' if 'RED' in piece_moving else 'RED'

        # Make copy of board so we don't mess up the real one if move is bad
        board = [row.copy() for row in self.board]
        captured = []
        # Go through moves
        keep_going = True
        current = start

        for next_place in move[1:]:
            if not keep_going:
                return False
            keep_going = False

            if next_place[0] < 0 or next_place[0] > 7 or next_place[1] < 0 or next_place[1] > 7:
                print(next_place, 'is not on the board')
                return False
            
            moved = False
            if color_moving == 'BLACK' or king_moving:
                if current[0] + 1 == next_place[0] and current[1] + 1 == next_place[1]:
                    # Down, right 1
                    if board[next_place[0]][next_place[1]] is not None:
                        return False
                    moved = True
                elif current[0] + 1 == next_place[0] and current[1] - 1 == next_place[1]:
                    # Down, left 1
                    if board[next_place[0]][next_place[1]] is not None:
                        return False
                    moved = True
                elif current[0] + 2 == next_place[0] and current[1] + 2 == next_place[1]:
                    # Down, right 2, capture
                    if opp_color not in str(board[current[0] + 1][current[1] + 1]):
                        return False
                    if board[next_place[0]][next_place[1]] is not None:
                        return False
                    captured.append((current[0] + 1, current[1] + 1))
                    board[current[0] + 1][current[1] + 1] = None
                    keep_going = True
                    moved = True
                elif current[0] + 2 == next_place[0] and current[1] - 2 == next_place[1]:
                    # Down, left 2, capture
                    if opp_color not in str(board[current[0] + 1][current[1] - 1]):
                        return False
                    if board[next_place[0]][next_place[1]] is not None:
                        return False
                    captured.append((current[0] + 1, current[1] - 1))
                    board[current[0] + 1][current[1] - 1] = None
                    keep_going = True
                    moved = True

            if (color_moving == 'RED' or king_moving) and not moved:
                if current[0] - 1 == next_place[0] and current[1] + 1 == next_place[1]:
                    # Up, right 1
                    if board[next_place[0]][next_place[1]] is not None:
                        return False
                    moved = True
                elif current[0] - 1 == next_place[0] and current[1] - 1 == next_place[1]:
                    # Up, left 1
                    if board[next_place[0]][next_place[1]] is not None:
                        return False
                    moved = True
                elif current[0] - 2 == next_place[0] and current[1] + 2 == next_place[1]:
                    # Up, right 2, capture
                    if opp_color not in str(board[current[0] - 1][current[1] + 1]):
                        return False
                    if board[next_place[0]][next_place[1]] is not None:
                        return False
                    captured.append((current[0] - 1, current[1] + 1))
                    board[current[0] - 1][current[1] + 1] = None
                    keep_going = True
                    moved = True
                elif current[0] - 2 == next_place[0] and current[1] - 2 == next_place[1]:
                    #Up, left 2, capture
                    if opp_color not in str(board[current[0] - 1][current[1] - 1]):
                        return False
                    if board[next_place[0]][next_place[1]]is not None:
                        return False
                    moved = True
                    captured.append((current[0] - 1, current[1] - 1))
                    board[current[0] - 1][current[1] - 1] = None
                    keep_going = True
                    moved = True

            if not moved:
                print('INVALID MOVE:', current, 'to', next_place)
                return False

            current = next_place

        # Multi-jump completion check
        if len(captured) > 0:
            # Check if the piece became a king during THIS move
            # If so, the rules say the move ends immediately
            end_r = current[0]
            just_kinged = (color_moving == 'BLACK' and end_r == 7) or (color_moving == 'RED' and end_r == 0)

            if not just_kinged:
                # Place the piece in its final hypothetical spot
                board[current[0]][current[1]] = piece_moving
                board[start[0]][start[1]] = None

                # If it can still jump from this final spot, they stopped part-way
                if self.piece_can_jump(current[0], current[1], color_moving, king_moving, board):
                    print("INCOMPLETE JUMP: You must take all available jumps in a multi-jump sequence.")
                    return False

        return move, captured

    def opponents_move(self, move_sequence, capture_sequence=None, time_remaining=None):
        '''Validates and applies the opponent's move, challenging if illegal.'''

        if not move_sequence or len(move_sequence) < 2:
            return (False, 1, "CHALLENGED AS ILLEGAL MOVE: Not enough coordinates.")

        # 1. Run their move through the validator to make sure they aren't cheating
        good_move = self.move_and_captures_if_good(move_sequence, self.opp_color)

        # If the validator says False, challenge it as an illegal move (Error Code 1)
        if not good_move:
            return (False, 1, "CHALLENGED AS ILLEGAL MOVE")

        validated_move, calculated_captures = good_move

        # 2. Check if they missed a mandatory jump (Error Code 3)
        # GEMINI EDIT: Use get_all_valid_moves to check for jumps
        _, jump_available = self.get_all_valid_moves(self.opp_color)
        if jump_available and len(calculated_captures) == 0:
            return (False, 3, "CHALLENGED AS JUMP ERROR: Opponent missed a mandatory jump.")

        # 3. If it passes both checks, it's a legal move
        moving_piece = self.board[validated_move[0][0]][validated_move[0][1]]

        # Remove piece from starting square
        self.board[validated_move[0][0]][validated_move[0][1]] = None

        # Remove any pieces they captured from our board
        for capture in calculated_captures:
            self.board[capture[0]][capture[1]] = None

        # Check for Kinging
        end_r = validated_move[-1][0]
        if (moving_piece == 'BLACK' and end_r == 7) or \
            (moving_piece == 'RED' and end_r == 0):
            moving_piece = f"{moving_piece}_KING"

        # Place the piece at the final destination
        self.board[end_r][validated_move[-1][1]] = moving_piece
        self.move_count += 1

        # Draw counter logic
        if len(calculated_captures) > 0:
            self.move_without_capture = 0
        else:
            self.move_without_capture += 1

        return (True, 0, f"Move to {validated_move[-1]} accepted.")


# Game status message helpers
def print_win():
    print("\nCONGRATULATIONS! YOU WON!")


def print_loss():
    print("\nYOU WERE DEFEATED.")


def print_draw():
    print("\nIT'S A DRAW! 20 MOVES WITHOUT CAPTURES.")


def process_game_over(player):
    '''Checks the status of the game and prints a message if the game has ended.'''
    status = player.check_game_over()
    if status == "WIN":
        print_win()
        return True
    elif status == "LOSS":
        print_loss()
        return True
    elif status == "DRAW":
        print_draw()
        return True
    return False

# Local command-line runner
if __name__ == '__main__':
    key = input("API Key: ")

    # Automatically set color based on command-line argument, defaulting to BLACK
    if len(sys.argv) > 1 and sys.argv[1].upper() in ['BLACK', 'RED']:
        my_color = sys.argv[1].upper()
    else:
        my_color = 'BLACK'
        
    print(f"\nYOUR COLOR: {my_color}")

    player = CheckersPlayer(my_color, gemma_key=key if key else None)

    is_my_turn = (player.color == 'BLACK')
    time_remaining = 300.0

    while True:
        # Failsafe check at the start of the loop
        if process_game_over(player): break

        if is_my_turn:
            # --- OUR AI'S TURN ---
            start = time.perf_counter()
            my_result = player.make_move(time_remaining)
            time_elapsed = (time.perf_counter() - start)
            time_remaining -= time_elapsed

            if not my_result:
                print("Failed to return a move.")
                break

            my_move, my_capture = my_result
            print(f"WE MOVED: {my_move} in {time_elapsed:0.2f}s")
            if my_capture: 
                print(f"*** CAPTURED: {my_capture} ***")

            # Check if our move just ended the game!
            if process_game_over(player): break

            is_my_turn = False

        else:
            # --- OPPONENT's TURN (VIA NETWORK) ---
            print(f"\n--- Waiting for opponent's move from standard input ---")
            ready, _, _ = select.select([sys.stdin], [], [], 300.0)

            if ready:
                opp_text = sys.stdin.readline()
                try:
                    opp_move = ast.literal_eval(opp_text.strip())
                    
                    # Validate the opponent's move and capture the status
                    valid_status, code, msg = player.opponents_move(opp_move)
                    
                    if valid_status:
                        print(f"ACCEPTED OPPONENT MOVE: {opp_move}")
                    else:
                        print(f"CHALLENGED OPPONENT MOVE: {msg}")
                        break # Stop the game if they tried to cheat!
                        
                except Exception as e:
                    print(f"Failed to parse opponent move. RECEIVED: '{opp_text.strip()}' | ERROR: {e}")
                    break
            else:
                print("\nTIMEOUT: No move received from opponent after 5 minutes. Stopping game.")
                break

            # Check if opponent's move just ended the game!
            if process_game_over(player): break

            is_my_turn = True