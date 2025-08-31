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
        x_range = word_info['x']
        y = int(word_info['y'])
        
        if '-' in x_range:
            x_start, x_end = map(int, x_range.split('-'))
            letters = []
            for x in range(x_start, x_end + 1):
                letter = grid[y-1][x-1]['Letter']
                letters.append(letter)
            return ''.join(letters)
        else:
            # Single column, down
            x = int(x_range)
            letters = []
            y_start, y_end = map(int, word_info['y'].split('-'))
            for yy in range(y_start, y_end + 1):
                letter = grid[yy-1][x-1]['Letter']
                letters.append(letter)
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
