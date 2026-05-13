# AI Checkers Player

A Python-based autonomous checkers player that uses Google's Gemma/Gemini API to select moves from a validated legal-move set.

## Features

- AI-generated move selection
- Full legal-move generation
- Mandatory jump enforcement
- Multi-jump detection and validation
- King promotion logic
- Opponent move validation
- Draw, win, and loss handling
- Local testing support

## Technologies

- Python
- Google GenAI API
- Regular expressions
- Depth-first search for multi-jump path generation

## How It Works

The program generates all valid moves from the current board state and asks the AI to choose from that legal move list. The selected move is parsed, checked against the allowed moves, revalidated against internal game logic, and then applied to the board.

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the program:

   ```bash
   python checkersplayer.py
   ```

3. Enter your Gemini API key when prompted.
