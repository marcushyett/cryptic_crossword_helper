#!/usr/bin/env python3
import json
import sys

def extract_answers(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    grid = data['data']['grid']
    words = {w['id']: w for w in data['data']['copy']['words']}
    clues = []
    
    # Collect all clues
    for group in data['data']['copy']['clues']:
        for clue in group['clues']:
            clues.append({
                'number': clue['number'],
                'clue': clue['clue'],
                'direction': group['title'].lower(),
                'word_id': clue['word'],
                'length': clue['length']
            })
    
    # Function to get word from positions
    def get_word(word_info):
        x = word_info['x']
        y = word_info['y']
        
        letters = []
        if '-' in x:
            # Across
            x_start, x_end = map(int, x.split('-'))
            y_pos = int(y)
            for col in range(x_start, x_end + 1):
                letter = grid[y_pos-1][col-1]['Letter']
                letters.append(letter)
        elif '-' in y:
            # Down
            x_pos = int(x)
            y_start, y_end = map(int, y.split('-'))
            for row in range(y_start, y_end + 1):
                letter = grid[row-1][x_pos-1]['Letter']
                letters.append(letter)
        else:
            # Single cell, shouldn't happen
            letters.append(grid[int(y)-1][int(x)-1]['Letter'])
        
        return ''.join(letters)
    
    # Add answers to clues
    for clue in clues:
        word_info = words[clue['word_id']]
        clue['answer'] = get_word(word_info)
    
    return {
        'title': data['data']['copy']['title'],
        'grid': grid,
        'clues': clues
    }

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python extract_answers.py <json_file>")
        sys.exit(1)
    
    result = extract_answers(sys.argv[1])
    print(json.dumps(result, indent=2))
