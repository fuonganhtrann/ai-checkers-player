# In the terminal, you must first run:
# pip install -q -U google-genai
import warnings
warnings.filterwarnings("ignore")

import ast
import sys
import select
import time
import re
import random 
import concurrent.futures  
from google import genai
from google.genai import types

class CheckersPlayer:
    '''A class that represents a player in a game of checkers'''

    # Contributors: [Your Name/Handle] & Gemini AI
    def __init__(self, color, gemma_key=None, team_name="snek_p"):
        self.color = color.upper()
        self.opp_color = 'RED' if self.color == 'BLACK' else 'BLACK'
        self.gemma_key = gemma_key
        self.client = None

        self.move_count = 0  
        self.move_without_capture = 0 

        # Initialize AI client and config
        if self.gemma_key:
            self.client = genai.Client(api_key=self.gemma_key)
            system_instructions = (
                f"You are playing checkers. You are player {self.color}. "
                f"Valid pieces to move are {self.color}. "
                "Determine the absolute best move. "
                "CRITICAL INSTRUCTION: Output your move as a sequence of coordinates. "
                "For a standard move, output two coordinates (e.g., '21 30'). "
                "For a multi-jump, output all coordinates in the chain (e.g., '63 41 23'). "
                "DO NOT output any other words, letters, or punctuation."
            )
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
                elif "KING" in p: row_disp.append(p[0].upper() + "K")
                else: row_disp.append(p[0].upper())
            formatted_row = "".join(f"{piece:>5}" for piece in row_disp)
            print(f"{i}{formatted_row}")

    def check_game_over(self):
        '''Checks if either player has run out of pieces or if a draw is reached'''
        if self.move_without_capture >= 20: return "DRAW"
        my_pieces = sum(1 for row in self.board for p in row if p and self.color in p)
        opp_pieces = sum(1 for row in self.board for p in row if p and self.color not in p)

        if my_pieces == 0: return "LOSS"
        if opp_pieces == 0: return "WIN"
        return None

    def piece_can_jump(self, r, c, color, is_king, current_board):
        opp_color = 'RED' if color == 'BLACK' else 'BLACK'
        directions = []
        if color == 'BLACK' or is_king: directions.extend([(2, 2), (2, -2)])
        if color == 'RED' or is_king: directions.extend([(-2, 2), (-2, -2)])

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            mid_r, mid_c = r + (dr // 2), c + (dc // 2)
            if 0 <= nr < 8 and 0 <= nc < 8 and current_board[nr][nc] is None:
                mid_piece = current_board[mid_r][mid_c]
                if mid_piece and opp_color in mid_piece:
                    return True
        return False
    
    def get_all_valid_moves(self, color):
        opp_color = 'RED' if color == 'BLACK' else 'BLACK'
        jumps = []
        normal_moves = []

        def get_jumps_from(r, c, is_king, current_board, current_path):
            found_further_jump = False
            jump_directions = []
            if color == 'BLACK' or is_king: jump_directions.extend([(2, 2), (2, -2)])
            if color == 'RED' or is_king: jump_directions.extend([(-2, 2), (-2, -2)])
            
            for dr, dc in jump_directions:
                nr, nc = r + dr, c + dc
                mid_r, mid_c = r + (dr // 2), c + (dc // 2)
                if 0 <= nr < 8 and 0 <= nc < 8 and current_board[nr][nc] is None:
                    mid_piece = current_board[mid_r][mid_c]
                    if mid_piece and opp_color in mid_piece:
                        found_further_jump = True
                        new_board = [row.copy() for row in current_board]
                        new_board[nr][nc] = current_board[r][c]
                        new_board[r][c] = None
                        new_board[mid_r][mid_c] = None
                        new_path = current_path + [f"{nr}{nc}"]

                        became_king = False
                        if not is_king and ((color == 'BLACK' and nr == 7) or (color == 'RED' and nr == 0)):
                            became_king = True
                            new_board[nr][nc] = f"{color}_KING"
                        
                        if became_king: jumps.append(" ".join(new_path))
                        else: get_jumps_from(nr, nc, is_king, new_board, new_path)

            if not found_further_jump and len(current_path) > 1:
                jumps.append(" ".join(current_path))

        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece and color in piece: 
                    is_king = 'KING' in piece
                    get_jumps_from(r, c, is_king, self.board, [f"{r}{c}"])

                    move_directions = []
                    if color == 'BLACK' or is_king: move_directions.extend([(1, 1), (1, -1)])
                    if color == 'RED' or is_king: move_directions.extend([(-1, 1), (-1, -1)])
                    for dr, dc in move_directions:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 8 and 0 <= nc < 8 and self.board[nr][nc] is None:
                            normal_moves.append(f"{r}{c} {nr}{nc}")

        if jumps: return jumps, True
        return normal_moves, False  

    def _get_instructions(self):
        board_lines = ["     0    1    2    3    4    5    6    7"]
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
        
        instructions = f"You are playing checkers. You are player {self.color}.\nThe current state of the board is:\n{board_txt}\n\n"
        if must_jump:
            instructions += f"*** CRITICAL: MANDATORY JUMP AVAILABLE! ***\nYou MUST capture an opponent's piece. Here are your FULL, valid jump chains: {', '.join(valid_steps)}\n"
        else:
            instructions += f"Here is a list of all legal standard moves you can choose from: {', '.join(valid_steps)}\nSelect the best strategic move from this list and output its coordinates. \n"

        instructions += "\nOutput ONLY your chosen coordinate sequence.\nDO NOT output any explanations, punctuation, or extra words."
        return instructions

    def _execute_move(self, move_str):
        '''Takes a string like "21 32", validates it, applies it to the board, and prints it.'''
        coords = move_str.split()
        move = [(int(c[0]), int(c[1])) for c in coords]
        
        good_move = self.move_and_captures_if_good(move, self.color)
        if not good_move: return False

        captures = good_move[1]
        moving = self.board[move[0][0]][move[0][1]]
        self.board[move[0][0]][move[0][1]] = None
        for capture in captures:
            self.board[capture[0]][capture[1]] = None
    
        end_r = move[-1][0]
        if (moving == 'BLACK' and end_r == 7) or (moving == 'RED' and end_r == 0):                    
            moving = f"{moving}_KING"
            print(f"PROMOTION! The piece is now a KING.")

        self.board[move[-1][0]][move[-1][1]] = moving
        self.move_count += 1

        if len(captures) > 0: self.move_without_capture = 0
        else: self.move_without_capture += 1

        print(move) 
        return good_move

    def make_move(self, seconds_remaining):
        '''Requests move from the AI autonomously with strict timeouts and failsafes.'''
        print(f"\n--- Your Turn ({self.color}) ---")
        self.print_board()

        turn_start_time = time.perf_counter()
        valid_moves, must_jump = self.get_all_valid_moves(self.color)

        # 1. FAST PATH
        if len(valid_moves) == 1:
            print(f"FAST PATH: Only one legal move! Skipping AI to save time.")
            return self._execute_move(valid_moves[0])

        # 2. TIME PANIC FAILSAFE (<45s for the whole game)
        if seconds_remaining < 45.0:
            print(f"TIME PANIC! Only {seconds_remaining:.1f}s left! Bypassing AI to survive.")
            return self._execute_move(random.choice(valid_moves))

        if not self.client:
            print("ERROR: AI is not initialized. An API key is required for autonomous play.")
            sys.exit(1)

        instructions = self._get_instructions()

        for attempt in range(15):
            
            # 3. PER-TURN TIMEOUT FAILSAFE (>15s on current turn)
            if time.perf_counter() - turn_start_time > 15.0:
                print(f"TURN TIMEOUT! AI took over 15 seconds. Playing a random move to keep the pace!")
                return self._execute_move(random.choice(valid_moves))

            try:
                # 4. API CALL WITH BACKGROUND THREAD TIMEOUT
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        self.client.models.generate_content,
                        model="gemma-4-26b-a4b-it",
                        contents=instructions,
                        config=self.ai_config
                    )
                    response = future.result(timeout=15.0)

                ai_text = response.text.strip() if response.text else ""
                print(f"[AI Attempt {attempt+1}]: {ai_text}")
                
                coords = re.findall(r'\b[0-7][0-7]\b', ai_text)
                move = [(int(coord[0]), int(coord[1])) for coord in coords]

                if len(move) < 2:
                    instructions += f"\nFORMAT ERROR: Could not parse '{ai_text}'. Output at least two coordinates like '21 30'."
                    continue

                move_str = " ".join(f"{r}{c}" for r, c in move)

                if move_str not in valid_moves:
                    matches = [v for v in valid_moves if v.startswith(move_str)]
                    if len(matches) == 1:
                        print(f"[Auto-Correct] Extending AI's partial move '{move_str}' to full jump '{matches[0]}'")
                        move_str = matches[0]
                    else:
                        instructions += f"\nINVALID MOVE: '{move_str}' is incomplete or illegal. You MUST choose from: {', '.join(valid_moves)}"
                        continue

                return self._execute_move(move_str)
                    
            except concurrent.futures.TimeoutError:
                print(f"\nTURN TIMEOUT: AI hanging! Falling back to a random legal move to keep pace.")
                return self._execute_move(random.choice(valid_moves))
                
            except Exception as e:
                error_msg = str(e)
                print(f"\n[API WARNING]: {error_msg}")
                
                # 5. SERVER CRASH FAILSAFE (3 Strikes)
                if attempt >= 2: 
                    print("FALLBACK ACTIVATED: API is unstable. Choosing a random legal move.")
                    return self._execute_move(random.choice(valid_moves))

                if "429" in error_msg:
                    wait_match = re.search(r'retry in (\d+\.?\d*)s', error_msg)
                    if wait_match:
                        wait_time = float(wait_match.group(1)) + 0.5 
                        print(f"Rate limited. Waiting {wait_time:.2f} seconds...")
                        time.sleep(wait_time)
                    else:
                        print("Rate limited. Pausing for 2 seconds...")
                        time.sleep(2)
                else:
                    print("Server glitch. Pausing for 1 second...")
                    time.sleep(1)
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
            
        start_piece = self.board[start[0]][start[1]]
        if start_piece is None or color not in start_piece:
            print('Cannot move from', start, 'as', color)
            return False

        piece_moving = self.board[move[0][0]][move[0][1]]
        king_moving = 'KING' in piece_moving
        color_moving = 'RED' if 'RED' in piece_moving else 'BLACK'
        opp_color = 'BLACK' if 'RED' in piece_moving else 'RED'

        board = [row.copy() for row in self.board]
        captured = []
        keep_going = True
        current = start

        for next_place in move[1:]:
            if not keep_going: return False
            keep_going = False

            if next_place[0] < 0 or next_place[0] > 7 or next_place[1] < 0 or next_place[1] > 7:
                print(next_place, 'is not on the board')
                return False
            
            moved = False
            if color_moving == 'BLACK' or king_moving:
                if current[0] + 1 == next_place[0] and current[1] + 1 == next_place[1]:
                    if board[next_place[0]][next_place[1]] is not None: return False
                    moved = True
                elif current[0] + 1 == next_place[0] and current[1] - 1 == next_place[1]:
                    if board[next_place[0]][next_place[1]] is not None: return False
                    moved = True
                elif current[0] + 2 == next_place[0] and current[1] + 2 == next_place[1]:
                    if opp_color not in str(board[current[0] + 1][current[1] + 1]): return False
                    if board[next_place[0]][next_place[1]] is not None: return False
                    captured.append((current[0] + 1, current[1] + 1))
                    board[current[0] + 1][current[1] + 1] = None
                    keep_going = True
                    moved = True
                elif current[0] + 2 == next_place[0] and current[1] - 2 == next_place[1]:
                    if opp_color not in str(board[current[0] + 1][current[1] - 1]): return False
                    if board[next_place[0]][next_place[1]] is not None: return False
                    captured.append((current[0] + 1, current[1] - 1))
                    board[current[0] + 1][current[1] - 1] = None
                    keep_going = True
                    moved = True

            if (color_moving == 'RED' or king_moving) and not moved:
                if current[0] - 1 == next_place[0] and current[1] + 1 == next_place[1]:
                    if board[next_place[0]][next_place[1]] is not None: return False
                    moved = True
                elif current[0] - 1 == next_place[0] and current[1] - 1 == next_place[1]:
                    if board[next_place[0]][next_place[1]] is not None: return False
                    moved = True
                elif current[0] - 2 == next_place[0] and current[1] + 2 == next_place[1]:
                    if opp_color not in str(board[current[0] - 1][current[1] + 1]): return False
                    if board[next_place[0]][next_place[1]] is not None: return False
                    captured.append((current[0] - 1, current[1] + 1))
                    board[current[0] - 1][current[1] + 1] = None
                    keep_going = True
                    moved = True
                elif current[0] - 2 == next_place[0] and current[1] - 2 == next_place[1]:
                    if opp_color not in str(board[current[0] - 1][current[1] - 1]): return False
                    if board[next_place[0]][next_place[1]]is not None: return False
                    captured.append((current[0] - 1, current[1] - 1))
                    board[current[0] - 1][current[1] - 1] = None
                    keep_going = True
                    moved = True

            if not moved:
                print('INVALID MOVE:', current, 'to', next_place)
                return False

            current = next_place

        if len(captured) > 0:
            end_r = current[0]
            just_kinged = (color_moving == 'BLACK' and end_r == 7) or (color_moving == 'RED' and end_r == 0)

            if not just_kinged:
                board[current[0]][current[1]] = piece_moving
                board[start[0]][start[1]] = None
                if self.piece_can_jump(current[0], current[1], color_moving, king_moving, board):
                    print("INCOMPLETE JUMP: You must take all available jumps in a multi-jump sequence.")
                    return False

        return move, captured

    def opponents_move(self, move_sequence, capture_sequence=None, time_remaining=None):
        if not move_sequence or len(move_sequence) < 2:
            return (False, 1, "CHALLENGED AS ILLEGAL MOVE: Not enough coordinates.")

        good_move = self.move_and_captures_if_good(move_sequence, self.opp_color)

        if not good_move: return (False, 1, "CHALLENGED AS ILLEGAL MOVE")

        validated_move, calculated_captures = good_move

        if capture_sequence is not None:
            set_declared = set(tuple(c) for c in capture_sequence)
            set_calculated = set(tuple(c) for c in calculated_captures)
            if set_declared != set_calculated:
                return (False, 4, f"CHALLENGED CAPTURE ERROR: Opponent claimed captures {capture_sequence} but actual captures are {calculated_captures}.")

        _, jump_available = self.get_all_valid_moves(self.opp_color)
        if jump_available and len(calculated_captures) == 0:
            return (False, 3, "CHALLENGED AS JUMP ERROR: Opponent missed a mandatory jump.")

        moving_piece = self.board[validated_move[0][0]][validated_move[0][1]]
        self.board[validated_move[0][0]][validated_move[0][1]] = None
        for capture in calculated_captures:
            self.board[capture[0]][capture[1]] = None

        end_r = validated_move[-1][0]
        if (moving_piece == 'BLACK' and end_r == 7) or (moving_piece == 'RED' and end_r == 0):
            moving_piece = f"{moving_piece}_KING"

        self.board[end_r][validated_move[-1][1]] = moving_piece
        self.move_count += 1

        if len(calculated_captures) > 0: self.move_without_capture = 0
        else: self.move_without_capture += 1

        return (True, 0, f"Move to {validated_move[-1]} accepted.")

def print_win():
   print(r"""
  _  _  ____  _  _   _    _  ____  _  _  _ 
 ( \/ )/ __ \( )( ) ( \/\/ )/ __ \( \( )( )
  \  /( (__) ))()(   )    (( (__) ))  ( (_) 
  (__) \____/ \__/  (__/\__)\____/(_)\_)(_)
    \o/ CONGRATULATIONS! YOU WON! \o/
   """)

def print_loss():
   print(r"""
  ____   __   __   _   _  __   __ 
 (  _ \ /  \ /  \ / )_( \/  \ /  \
  ) _ ((  O (  O )) __  (  O (  O )
 (____/ \__/ \__/ \_) (_/\__/ \__/
      T_T YOU WERE DEFEATED T_T
   """)

def print_draw():
   print(r"""
 ____  ____    __    _    _
(  _ \(  _ \  /__\  ( \/\/ )
)(_) ))  - / /(__)\  )    (
(____/(_)\_)(__)(__)(__/\__)
o_o IT'S A DRAW! 20 MOVES NO CAPTURES o_o
   """)

def process_game_over(player):
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

# GAME MAIN BLOCK
if __name__ == '__main__':
    key = input("API Key (Press Enter to skip AI): ")

    if len(sys.argv) > 1 and sys.argv[1].upper() in ['BLACK', 'RED']:
        my_color = sys.argv[1].upper()
    else:
        my_color = 'BLACK'
        
    print(f"\nYou are playing as {my_color}!")

    player = CheckersPlayer(my_color, gemma_key=key if key else None)

    is_my_turn = (player.color == 'BLACK')
    time_remaining = 300.0

    while True:
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
            print(f"We moved: {my_move} in {time_elapsed:0.2f}s")
            if my_capture: 
                print(f"JUMPED: {my_capture}")

            if process_game_over(player): break

            is_my_turn = False

        else:
            # --- OPPONENT's TURN (VIA NETWORK) ---
            print(f"\n--- Waiting for opponent's move from coordinator ---")
            ready, _, _ = select.select([sys.stdin], [], [], 300.0)

            if ready:
                opp_text = sys.stdin.readline()
                try:
                    opp_move = ast.literal_eval(opp_text.strip())
                    
                    valid_status, code, msg = player.opponents_move(opp_move)
                    
                    if valid_status:
                        print(f"Opponent move {opp_move} Accepted.")
                    else:
                        print(f"CHALLENGED OPPONENT MOVE: {msg}")
                        break 
                        
                except Exception as e:
                    print(f"Failed to parse opponent move. RECEIVED: '{opp_text.strip()}' | ERROR: {e}")
                    break
            else:
                print("\nTIMEOUT: No move received from opponent after 5 minutes. Stopping game.")
                break

            if process_game_over(player): break

            is_my_turn = True