from gevent.pywsgi import WSGIServer
from main import app
from gevent import monkey
import flask
import base64
import random
import time
from geventwebsocket.handler import WebSocketHandler
import chess    
from chess import Board, Move, STARTING_FEN
import sys
from flask_cors import CORS, cross_origin
import signal
from contextlib import contextmanager
import chess.polyglot
        
        
MAX_DEPTH = 18
        
app = flask.Flask(__name__)

square_table = {chess.PAWN:[
 0,  0,  0,  0,  0,  0,  0,  0,
 5, 10, 10,-20,-20, 10, 10,  5,
 5, -5,-10,  0,  0,-10, -5,  5,
 0,  0,  0, 20, 20,  0,  0,  0,
 5,  5, 10, 25, 25, 10,  5,  5,
10, 10, 20, 30, 30, 20, 10, 10,
50, 50, 50, 50, 50, 50, 50, 50,
 0,  0,  0,  0,  0,  0,  0,  0], chess.KNIGHT: [
-50,-40,-30,-30,-30,-30,-40,-50,
-40,-20,  0,  5,  5,  0,-20,-40,
-30,  5, 10, 15, 15, 10,  5,-30,
-30,  0, 15, 20, 20, 15,  0,-30,
-30,  5, 15, 20, 20, 15,  5,-30,
-30,  0, 10, 15, 15, 10,  0,-30,
-40,-20,  0,  0,  0,  0,-20,-40,
-50,-40,-30,-30,-30,-30,-40,-50], chess.BISHOP: [
-20,-10,-10,-10,-10,-10,-10,-20,
-10,  5,  0,  0,  0,  0,  5,-10,
-10, 10, 10, 10, 10, 10, 10,-10,
-10,  0, 10, 10, 10, 10,  0,-10,
-10,  5,  5, 10, 10,  5,  5,-10,
-10,  0,  5, 10, 10,  5,  0,-10,
-10,  0,  0,  0,  0,  0,  0,-10,
-20,-10,-10,-10,-10,-10,-10,-20], chess.ROOK: [
  0,  0,  0,  5,  5,  0,  0,  0,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
 -5,  0,  0,  0,  0,  0,  0, -5,
  5, 10, 10, 10, 10, 10, 10,  5,
 0,  0,  0,  0,  0,  0,  0,  0], chess.QUEEN: [
-20,-10,-10, -5, -5,-10,-10,-20,
-10,  0,  0,  0,  0,  0,  0,-10,
-10,  5,  5,  5,  5,  5,  0,-10,
  0,  0,  5,  5,  5,  5,  0, -5,
 -5,  0,  5,  5,  5,  5,  0, -5,
-10,  0,  5,  5,  5,  5,  0,-10,
-10,  0,  0,  0,  0,  0,  0,-10,
-20,-10,-10, -5, -5,-10,-10,-20], chess.KING: [
 20, 30, 10,  0,  0, 10, 30, 20,
 20, 20,  0,  0,  0,  0, 20, 20,
-10,-20,-20,-20,-20,-20,-20,-10,
-20,-30,-30,-40,-40,-30,-30,-20,
-30,-40,-40,-50,-50,-40,-40,-30,
-30,-40,-40,-50,-50,-40,-40,-30,
-30,-40,-40,-50,-50,-40,-40,-30,
-30,-40,-40,-50,-50,-40,-40,-30]}



def order_moves(board, moves):
    scores = {}
    for move in moves:
        board.push(move)
        if board.turn:
            scores[move] = -sys.maxsize
        else:
            scores[move] = sys.maxsize
        for second_move in board.legal_moves:
            board.push(second_move)
            score = calculate_board_score(board)
            if score > scores[move]:
                scores[move] = score
            board.pop()
        board.pop()
    new_moves = []
    for i in range(len(scores)):
        if board.turn:
            min_item = max(scores, key=scores.get)
        else:
            min_item = min(scores, key=scores.get)
        new_moves.append(min_item)
        del scores[min_item]
    return new_moves

def generate_legal_moves(board):
    moves = board.pseudo_legal_moves
    new_moves = []
    for move in moves:
        if board.is_legal(move):
            new_moves.append(move)
    return new_moves

def calculate_board_score(board):
    
    if board.is_checkmate():
        if board.turn:
            return -sys.maxsize
        else:
            return sys.maxsize
    elif board.is_stalemate():
        return -50  # worth nothing, draw
    
    w = {"p":len(board.pieces(chess.PAWN, chess.WHITE))*100, "n":len(board.pieces(chess.KNIGHT, chess.WHITE))*320, "b":len(board.pieces(chess.BISHOP, chess.WHITE))*330, "r":len(board.pieces(chess.ROOK, chess.WHITE))*900, "q":len(board.pieces(chess.QUEEN, chess.WHITE))*900}
    b = {"p":len(board.pieces(chess.PAWN, chess.BLACK))*100, "n":len(board.pieces(chess.KNIGHT, chess.BLACK))*320, "b":len(board.pieces(chess.BISHOP, chess.BLACK))*330, "r":len(board.pieces(chess.ROOK, chess.BLACK))*900, "q":len(board.pieces(chess.QUEEN, chess.BLACK))*900}
    
    material = (w['p'] - b['p']) + (w['n'] - b['n']) + (w['b'] - b['b']) + (w['r'] - b['r']) + (w['q'] - b['q'])
    
    piece_dict = {chess.PAWN:0, chess.KNIGHT:0, chess.BISHOP:0, chess.ROOK:0, chess.QUEEN:0}
    for piece_type in piece_dict:
        for piece in board.pieces(piece_type, chess.WHITE):
            piece_dict[piece_type] += square_table[piece_type][piece]
        for piece in board.pieces(piece_type, chess.BLACK):
            piece_dict[piece_type] -= (square_table[piece_type][chess.square_mirror(piece)])

    score = material + sum(piece_dict.values())
    
    if board.turn:
        return score
    else:
        return -score
    
def prune(board, alpha_value, beta_value, depth=0, maxdepth=MAX_DEPTH):
    if depth >= maxdepth:
        return q_search(board, alpha_value=alpha_value, beta_value=beta_value)
    else:
        best_score = -sys.maxsize
        for move in generate_legal_moves(board):
            board.push(move)   
            score = -prune(board, -beta_value, -alpha_value, depth=depth+1)
            board.pop()
            if score >= beta_value:
                return score
            if score > best_score:
                best_score = score
            if score > alpha_value:
                alpha_value = score   
        return best_score



## see https://www.chessprogramming.org/Quiescence_Search for explanation

def q_search(board, alpha_value=0, beta_value=0):
    stand_pat = calculate_board_score(board)
    if( stand_pat >= beta_value ):
        return beta_value
    if( alpha_value < stand_pat ):
        alpha_value = stand_pat

    for move in generate_legal_moves(board):
        if board.is_capture(move):
            board.push(move)        
            score = -q_search(board, alpha_value=-beta_value, beta_value=-alpha_value) # negamax swap
            board.pop()
            if score >= beta_value:
                return beta_value
            if score > alpha_value:
                alpha_value = score  
    return alpha_value



def iterate_legal_moves(board, best_value=0, alpha_value=0, beta_value=0, depth=0, maxdepth=MAX_DEPTH):
    for move in order_moves(board, generate_legal_moves(board)):
        board.push(move)
        board_value = -prune(board, -beta_value, -alpha_value, depth=depth+1, maxdepth=maxdepth)
        if board_value > best_value:
            best_value = board_value;
            best_idx_value = move
        if( board_value > alpha_value ):
            alpha_value = board_value
        board.pop()
    return best_idx_value
    

def calculate_best_move(board, maxdepth=MAX_DEPTH):
    try:
        time.sleep(0.33)
        best_move = chess.polyglot.MemoryMappedReader("bookfish.bin").weighted_choice(board).move
    except Exception as e:
        best_move = iterate_legal_moves(board, best_value=-sys.maxsize, alpha_value=-sys.maxsize, beta_value=sys.maxsize, maxdepth=maxdepth)
    return best_move
    

    
def calculate(FEN):
    board = Board(FEN)

    best_move = calculate_best_move(board)

    board.push(best_move)
    if board.is_game_over():
        return "~{}".format(board.fen())      # ~ indicates game ending for use in frontend, can be ignored/removed without error
    else:
        return "{}".format(board.fen())


@app.route("/fen/<fen>", methods=["POST"])
def api_fen(fen):
    try:
        fen = base64.b64decode(fen).decode()
        print(fen)
        return "{}".format(calculate(fen))
    except Exception as e:
        print(str(e))
        return "N/A", 404


cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.run(host="0.0.0.0", port=8887)

# do not run this in production !! use a proxy instead
